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
    description="""Sonify a network capture. Pipe in stdout from TShark to convert different
protocol messages into different sounds. Tshark should be invoked with the arguments
'-q -l -T fields -e frame.protocols -e ip.addr -e ipv6.addr'.""",
    epilog="""Volume is in the range 0-127.
When providing dictionaries in Windows ensure there are no spaces and that quotes are escaped with a backslash.""",
)
parser.add_argument("-v", help="Verbose", action="store_true")
parser.add_argument(
    "-P", help="Sonify based on default protocol mapping", action="store_true"
)
parser.add_argument(
    "-I", help="Sonify based on default IP address mapping", action="store_true"
)
parser.add_argument(
    "--protocol",
    help="""Protocol to instrument mapping. This is a dictionary in the format
{"protocol": ["instrument", volume]}
""",
    type=json.loads,
)
parser.add_argument(
    "--ip",
    help="""IP address or network to instrument mapping. This is a dictionary in the format
{"ip address": ["instrument", volume]}
Prefix IP address with 'src' to match only source or 'dst' to match only destination.
""",
    type=json.loads,
)
parser.add_argument("-l", help="List available instruments", action="store_true")
parser.add_argument("-i", help="Interface to capture from", type=str, required=True)
parser.add_argument(
    "targs", help="Additional arguments to TShark. Precede arguments with --", nargs="*"
)
parser.add_argument(
    "-t",
    help="TShark location (defaults to %%PROGRAMFILES%% on Windows and on path in *nix)",
    type=str,
)
args = parser.parse_args()
verbose = args.v
protocol = args.P
ip = args.I
protocolMap = args.protocol
ipMap = args.ip
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
# protocol to instrument
if protocol:
    protocolMap = {
        "mdns": ["tinkle bell", 50],
        "tls": ["blown bottle", 50],
        "arp": ["hi wood block", 100],
        "icmp": ["gunshot", 127],
        "dns": ["trumpet", 80],
    }

# ip address to instrument
if ip:
    ipMap = {
        "src10.0.0.0/8": ["flute", 100],
        "src172.16.0.0/12": ["flute", 100],
        "src192.168.0.0/16": ["flute", 100],
        "dst10.0.0.0/8": ["xylophone", 100],
        "dst172.16.0.0/12": ["xylophone", 100],
        "dst192.168.0.0/16": ["xylophone", 100],
    }


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


def play(instrument, volume):
    # play a note for a while
    global stopping
    if not stopping:
        thread = threading.Thread(target=playThread, args=(instrument, volume))
        thread.start()
        activeNotes.append(thread)


def playThread(instrument, volume):
    if instrument in melodic:
        # melodic
        instrumentnum = melodic[instrument] - 1
        pitch = 72
        channel = 0
        midiOut.set_instrument(instrumentnum, channel)
    elif instrument in percussion:
        # percussion
        instrumentnum = percussion[instrument]
        pitch = instrumentnum
        channel = 9
    else:
        print("Error: {} not recognized".format(instrument))
        sys.exit()

    midiOut.note_on(pitch, volume, channel)
    sleep(0.5)
    midiOut.note_off(pitch, volume, channel)
    # this should be the first thread in the list, so remove that
    activeNotes.pop(0)


# Handle Ctrl-C press
stopping = False
signal.signal(signal.SIGINT, cleanExit)

# Start TShark
cmd = [
    tshark,
    "-i",
    interface,
    "-l",
    "-Q",
    "-T",
    "fields",
    "-e",
    "frame.protocols",
    "-e",
    "ip.addr",
    "-e",
    "ipv6.addr",
]
if targs:
    cmd += targs
if verbose:
    print("Starting TShark with {}".format(cmd))
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
    if verbose:
        print(">> {}".format(line.strip()))
    if re.search(r"\S\s+\S", line):
        # protocol + IP
        protocolStr, ipStr = line.strip().split()
    else:
        # will only get protocols if this is eg ARP
        protocolStr = line.strip()
        ipStr = None
    protocols = protocolStr.split(":")
    if ipStr:
        ips = ipStr.split(",")
        if len(ips) > 2:
            # IP in IP, eg ICMP packet with original request
            ips = ips[0:2]
    else:
        ips = None

    # Check if protocol is known (get first matching protocol)
    if protocolMap:
        found = False
        for protocol in protocols:
            if protocol in protocolMap:
                found = True
                instrument, volume = protocolMap.get(protocol)
                print("{}: {}".format(protocol, instrument))
                play(instrument, volume)
                break
        if not found:
            print("{}: -".format(protocol))

    # Check if IP is known (get first matching IP)
    if ipMap and ips:
        found = False
        src, dst = list(map(ipaddress.ip_address, ips))
        for ip in ipMap.keys():
            if (
                (ip.startswith("src") and src in ipaddress.ip_network(ip[3:]))
                or (ip.startswith("dst") and dst in ipaddress.ip_network(ip[3:]))
                or (
                    ip[0:3] not in ["src", "dst"]
                    and (
                        src in ipaddress.ip_network(ip)
                        or dst in ipaddress.ip_network(ip)
                    )
                )
            ):
                found = True
                instrument, volume = ipMap.get(ip)
                print("{}: {}".format(ip, instrument))
                play(instrument, volume)
                break
        if not found:
            print("{}: -".format(ip))

cleanExit()
