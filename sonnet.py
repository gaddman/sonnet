#! python3.7
# Using python3.7 on Windows because pygame.midi doesn't work on 3.8

# Sonify a network capture
# https://github.com/gaddman/sonnet
# Christopher Gadd
# 2019

import argparse
import collections
import ipaddress
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import textwrap
import threading
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi as midi

from constants import *

Note = collections.namedtuple("Note", ["instrument", "pitch", "volume"])

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description="""Sonify a network capture. Uses TShark to capture traffic and plays
different sounds based on packet information such as IP address or protocol.""",
    epilog="""
Trigger     in the format  <Wireshark display field> <operator> <value>, eg "ip.addr == 8.8.8.8" or a protocol, eg "icmp"
Instrument  string, use -l to list available instruments
Pitch       integer from 21-108, see https://newt.phys.unsw.edu.au/jw/notes.html for mapping to note names
Volume      integer from 0-127

When providing dictionaries in Windows use triple quotes around strings.""",
)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument(
    "-s", help="Sonify based on default mappings - either 'protocol', 'ip', or 'tcp'", type=str,
)
group.add_argument(
    "-m",
    help="""Instrument mapping. This is a dictionary in the format
{trigger: [instrument, pitch, volume]}""",
    type=json.loads,
)
group.add_argument(
    "-f", help="Load mapping from file, format as above", type=str,
)
parser.add_argument("-l", help="List available instruments", action="store_true")
parser.add_argument(
    "-b",
    help="""Align the notes to a beat interval. A string in the format 'tempo "instrument" pitch volume'
or just tempo if no instrument is to be played. The tempo is an integer in beats per minute.""",
    type=str,
)
parser.add_argument("-i", help="Interface to capture from", type=str, required=True)
parser.add_argument(
    "targs", help="Additional arguments to TShark. Precede arguments with --", nargs="*"
)
parser.add_argument(
    "-t",
    help="TShark location (defaults to %%PROGRAMFILES%% on Windows and on path in *nix)",
    type=str,
)
parser.add_argument("-v", help="Verbose, use twice for more verbosity", action="count", default=0)

args = parser.parse_args()
verbose = args.v
inputMap = args.m
fileMap = args.f
sampleMap = args.s
drum = args.b
listing = args.l
interface = args.i
targs = args.targs
tshark = args.t

if listing:
    print("Instrument listing")
    print("Melodic:")
    print(list(melodic.keys()))
    print("Percussion:")
    print(list(percussion.keys()))
    sys.exit()

if not tshark:
    # determine path for tshark binary
    if os.name == "nt":
        # Windows, could be 32-bit or 64-bit TShark installed
        t32 = os.path.expandvars("%PROGRAMFILES(X86)%\\Wireshark\\tshark.exe")
        t64 = os.path.expandvars("%PROGRAMFILES%\\Wireshark\\tshark.exe")
        if os.path.exists(t64):
            tshark = t64
        elif os.path.exists(t32):
            tshark = t32
        else:
            sys.exit("Can't locate TShark executable")
    else:
        # Assume tshark is on the path
        tshark = "tshark"

if drum:
    if drum.isdigit():
        # No instrument, beat frequency only
        tempo = int(drum)
        note = None
    else:
        # Parse string for 'tempo "instrument" pitch volume'
        try:
            d = shlex.split(drum)
            tempo = int(d[0])
            note = Note(d[1], int(d[2]), int(d[3]))
        except:
            sys.exit("Can't parse drumbeat '{}'".format(drum))
        if note.instrument not in melodic and note.instrument not in percussion:
            sys.exit("Error: instrument '{}' not recognized".format(note.instrument))

    beatFreq = 60 / tempo  # seconds between beats
    beat = (beatFreq, note)

# Sample mappings
if sampleMap:
    if sampleMap in sampleMaps:
        inputMap = sampleMaps[sampleMap]
    else:
        sys.exit("Unknown mapping: {}".format(sampleMap))

# Load mappings from file
if fileMap:
    if not os.path.exists(fileMap):
        sys.exit("Can't locate file '{}'".format(fileMap))
    with open(fileMap, "r") as f:
        try:
            inputMap = json.loads(f.read())
        except json.decoder.JSONDecodeError as err:
            sys.exit("Can't read file: {}".format(err))


def numeric(s):
    # if string is a number then convert it
    try:
        return float(s)
    except ValueError:
        return s


# Parse mapping to sanitize and determine fields to capture
mapping = {}
for match, noteList in inputMap.items():
    note = Note(*noteList)
    if "." not in match:
        # must(?) be a protocol name
        if "frame.protocols" not in mapping:
            mapping["frame.protocols"] = {}
        mapping["frame.protocols"].update({match: note})
    else:
        fieldName, operator, value = re.search(r"(^[^=!<> ]+)\s*([=!<>]+)\s*(.+)", match).groups()
        if operator not in ops.keys():
            sys.exit("Invalid operator '{}' in '{}'".format(operator, match))
        if fieldName not in mapping:
            mapping[fieldName] = {}
        mapping[fieldName].update({tuple([operator, numeric(value)]): note})
    if note.instrument not in melodic and note.instrument not in percussion:
        sys.exit("Error: instrument '{}' not recognized".format(note.instrument))

if verbose:
    print("Mapping fields to instruments:")
    for field, matches in mapping.items():
        print(" - {}:".format(field))
        for match, note in matches.items():
            print("\t{}: {}".format(match, list(note)))
fieldList = sorted(mapping.keys())


def cleanExit(signal=None, frame=None):
    # Probably pressed Ctrl-C, try to gracefully exit.
    # Wait for already playing notes to complete
    global stopping
    if not stopping:
        stopping = True
        if drum:
            beatTimer.cancel()
        for thread in list(activeNotes):
            if thread.is_alive():
                thread.join()
        midiOut.close()
        midi.quit()


class repeatTimer(threading.Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


def drumbeat():
    # play drumbeat and all queued notes
    global queuedNotes
    if beat[1]:
        # Play an instrument each beat
        queuedNotes.append(beat[1])
    # Play queued notes. Increase volume for each note in the queue
    # queue is a dictionary of key=note(a named tuple): value=volume
    queue = {}
    for note in queuedNotes:
        if note not in queue:
            queue[note] = note.volume
        else:
            # max volume is 127, increase by 2 for each note in this interval
            queue[note] = min(127, queue[note] + 2)
    queuedNotes = []
    if verbose:
        print("Beat:")
    for note, volume in queue.items():
        newNote = Note(note.instrument, note.pitch, volume)
        thread = threading.Thread(target=playThread, args=(newNote,))
        activeNotes.append(thread)
        if verbose:
            print("  {} with volume {}".format(list(newNote), volume))
        thread.start()


def play(note):
    # play a note for a while
    global stopping
    global queuedNotes
    if not stopping:
        if drum:
            # Drumbeat function will play the note later.
            queuedNotes.append(note)
        else:
            # play immediately
            thread = threading.Thread(target=playThread, args=(note,))
            activeNotes.append(thread)
            thread.start()


def playThread(note):
    if note.instrument in melodic:
        # melodic
        instrumentnum = melodic[note.instrument] - 1
        pitch = note.pitch
        channel = 0
        midiOut.set_instrument(instrumentnum, channel)
    elif note.instrument in percussion:
        # percussion
        instrumentnum = percussion[note.instrument]
        pitch = instrumentnum
        channel = 9

    midiOut.note_on(pitch, note.volume, channel)
    time.sleep(0.5)
    midiOut.note_off(pitch, note.volume, channel)
    # this should be the first thread in the list, so remove that
    activeNotes.pop(0)


# Handle Ctrl-C press
stopping = False
signal.signal(signal.SIGINT, cleanExit)

# Start TShark
cmd = [tshark, "-i", interface, "-l", "-Q", "-T", "fields"]
for fieldName in fieldList:
    cmd += ["-e", fieldName]
if targs:
    cmd += targs
if verbose:
    print("Starting TShark with '{}'".format(" ".join(cmd)))
try:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
except FileNotFoundError:
    sys.exit("Unable to locate TShark executable at {}".format(tshark))

# Set up midi
midi.init()
port = midi.get_default_output_id()
if verbose:
    print("Outputting to {}".format(midi.get_device_info(port)))
midiOut = midi.Output(port)

if drum:
    beatTimer = repeatTimer(beat[0], drumbeat)
    beatTimer.start()


activeNotes = []  # threads currently playing
queuedNotes = []  # notes to play
for line in p.stdout:
    if stopping:
        continue

    # TShark output is tab delimited
    capture = line.strip("\n").split("\t")
    if verbose >= 2:
        print(">> {}".format(capture))

    # Loop through each field of the output
    for index, fieldName in enumerate(fieldList):
        if capture[index] == "":
            # TShark didn't find this field in the packet
            continue
        else:
            captureField = capture[index]
            matchFound = False

        # Loop through each defined match
        for match, note in mapping[fieldName].items():
            if fieldName == "frame.protocols":
                # Special case, no operator/value combo
                protocols = captureField.split(":")
                for protocol, note in mapping[fieldName].items():
                    if protocol in protocols:
                        matchFound = True
                        break
            else:
                operator, value = match
                if fieldName in ipFields:
                    # Special case, convert to IP
                    if "," in captureField:
                        # IP in IP, eg ICMP packet with original request
                        captureField = captureField.split(",")[0]
                    # Limited set of operators for IP comparison
                    if (
                        operator == "=="
                        and ipaddress.ip_address(captureField) in ipaddress.ip_network(value)
                    ) or (
                        operator == "!="
                        and ipaddress.ip_address(captureField) not in ipaddress.ip_network(value)
                    ):
                        matchFound = True
                        break
                else:
                    # Anything except IP address or protocol is compared here
                    op_func = ops[operator]
                    if op_func(numeric(captureField), value):
                        matchFound = True
                        break
        if matchFound:
            if verbose:
                if isinstance(match, tuple):
                    matchStr = "{} {} {}".format(fieldName, match[0], str(match[1]))
                else:
                    matchStr = protocol
                print("{}: '{}' pitch:{} volume:{}".format(matchStr, *note))
            play(note)

cleanExit()
