#! python3.7
# Using python3.7 on Windows because pygame.midi doesn't work on 3.8

# Sonify a network capture

import argparse
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
from time import sleep

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi as midi

from constants import *

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description="""Sonify a network capture. Uses TShark to capture traffic and plays
different sounds based on packet information such as IP address or protocol.""",
    epilog="""
Trigger     in the format  <Wireshark display field> <operator> <value>, eg "ip.addr == 8.8.8.8" or a protocol, eg "icmp"
Instrument  string, use -l to list available instruments
Pitch       integer from 21-108, see https://newt.phys.unsw.edu.au/jw/notes.html for mapping to note names
Volume      integer from 0-127

When providing dictionaries in Windows ensure there are no spaces and that quotes are escaped with a backslash.""",
)
parser.add_argument("-v", help="Verbose", action="store_true")
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument(
    "-s", help="Sonify based on default mappings - either 'protocol' or 'ip'", type=str,
)
group.add_argument(
    "-m",
    help="""Instrument mapping. This is a dictionary in the format
{trigger: [instrument, pitch, volume]}""",
    type=json.loads,
)
group.add_argument("-f", help="""Load mapping from file, format as above""", type=str,)
parser.add_argument("-l", help="List available instruments", action="store_true")
parser.add_argument("-i", help="Interface to capture from", type=str, required=True)
parser.add_argument("targs", help="Additional arguments to TShark. Precede arguments with --", nargs="*")
parser.add_argument(
    "-t",
    help="TShark location (defaults to %%PROGRAMFILES%% on Windows and on path in *nix)",
    type=str,
)
args = parser.parse_args()
verbose = args.v
inputMap = args.m
fileMap = args.f
sampleMap = args.s
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

# Default mappings if nothing specified
if sampleMap:
    if sampleMap in sampleMaps:
        inputMap = sampleMaps[sampleMap]
    else:
        sys.exit("Unknown mapping: {}".format(sampleMap))

# Load mappings from file
if fileMap:
    if not os.path.exists(fileMap):
        sys.exit("Can't locate file '{}'".format(fileMap))
    with open(fileMap, 'r') as f:
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
for match, note in inputMap.items():
    if "." not in match:
        # must(?) be a protocol name
        if "frame.protocols" not in mapping:
            mapping["frame.protocols"] = {}
        mapping["frame.protocols"].update({match: note})
    else:
        fieldName, operator, value = re.search(
            r"(^[^=!<> ]+)\s*([=!<>]+)\s*(.+)", match
        ).groups()
        if operator not in ops.keys():
            sys.exit("Invalid operator '{}' in '{}'".format(operator, match))
        if fieldName not in mapping:
            mapping[fieldName] = {}
        mapping[fieldName].update({tuple([operator, numeric(value)]): note})
    instrument=note[0]
    if instrument not in melodic and instrument not in percussion:
        sys.exit("Error: {} not recognized".format(instrument))

if verbose:
    print("Mapping fields to instruments:")
    for key, value in mapping.items():
        print(" - {}:".format(key))
        for key, value in value.items():
            print("\t{}: {}".format(key, value))
fieldList = sorted(mapping.keys())


def cleanExit(signal=None, frame=None):
    # Probably pressed Ctrl-C, try to gracefully exit.
    # Wait for already playing notes to complete
    global stopping
    if not stopping:
        stopping = True
        for thread in list(activeNotes):
            thread.join()
        midiOut.close()
        midi.quit()


def play(instrument,pitch, volume):
    # play a note for a while
    global stopping
    if not stopping:
        thread = threading.Thread(target=playThread, args=(instrument,pitch, volume))
        thread.start()
        activeNotes.append(thread)


def playThread(instrument,pitch, volume):
    if instrument in melodic:
        # melodic
        instrumentnum = melodic[instrument] - 1
        channel = 0
        midiOut.set_instrument(instrumentnum, channel)
    elif instrument in percussion:
        # percussion
        instrumentnum = percussion[instrument]
        pitch = instrumentnum
        channel = 9

    midiOut.note_on(pitch, volume, channel)
    sleep(0.5)
    midiOut.note_off(pitch, volume, channel)
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


activeNotes = []
for line in p.stdout:
    if stopping:
        continue

    # TShark output is tab delimited
    capture = line.strip("\n").split("\t")
    if verbose:
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
                        and ipaddress.ip_address(captureField)
                        in ipaddress.ip_network(value)
                    ) or (
                        operator == "!="
                        and ipaddress.ip_address(captureField)
                        not in ipaddress.ip_network(value)
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
            instrument, pitch, volume = note
            if verbose:
                if isinstance(match, tuple):
                    matchStr = "{} {} {}".format(fieldName, match[0], str(match[1]))
                else:
                    matchStr = protocol
                print(
                    "{}: '{}' pitch:{} volume:{}".format(
                        matchStr, instrument, pitch, volume
                    )
                )
            play(instrument, pitch,volume)

cleanExit()
