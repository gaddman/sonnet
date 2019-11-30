#! python3.7
# Using python3.7 on Windows because pygame.midi doesn't work on 3.8

# Sonify a Wireshark capture
#
# Pipe Tshark in, eg start with:
# Windows Command:
#   "C:\Program Files\Wireshark\tshark.exe" -i Ethernet -q -l -T tabs -T fields -e frame.protocols -e ip.addr -e ipv6.addr | py .\sonnet.py
# Windows PowerShell:
#   Nope, run via cmd. See https://stackoverflow.com/questions/27440768/powershell-piping-causes-explosive-memory-usage/28058958#28058958

import argparse
import ipaddress
import json
import os
import re
import signal
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
    "-p", help="Sonify based on default protocol mapping", action="store_true"
)
parser.add_argument(
    "-i", help="Sonify based on default IP address mapping", action="store_true"
)
parser.add_argument(
    "-P",
    help="""Protocol to instrument mapping. This is a dictionary in the format
{"protocol": ["instrument", volume]}
""",
    type=json.loads,
)
parser.add_argument(
    "-I",
    help="""IP address or network to instrument mapping. This is a dictionary in the format
{"ip address": ["instrument", volume]}
Prefix IP address with 'src' to match only source or 'dst' to match only destination.
""",
    type=json.loads,
)
parser.add_argument("-l", help="List available instruments", action="store_true")
args = parser.parse_args()
verbose = args.v
protocol = args.p
ip = args.i
protocolMap = args.P
ipMap = args.I
listing = args.l

if listing:
    print("Instrument listing")
    print("Melodic:")
    print(list(melodic.keys()))
    print("Percussion:")
    print(list(percussion.keys()))
    sys.exit()

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


def clean_exit(signal,frame):
    # Probably pressed Ctrl-C, try to gracefully exit.
    # try/except in case pressed twice quickly and midi already closed
    try:
        midiOut.close()
        midi.quit()
    except:
        pass
    sys.exit(0)


def play(instrument, volume):
    # play a note for a while
    # Notes from http://computermusicresource.com/midikeys.html
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


# Handle Ctrl-C press
signal.signal(signal.SIGINT, clean_exit)

# Set up midi
midi.init()
port = midi.get_default_output_id()
if verbose:
    print("Outputting to {}".format(midi.get_device_info(port)))
midiOut = midi.Output(port)

for line in sys.stdin:
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
                threading.Thread(target=play, args=(instrument, volume)).start()
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
                threading.Thread(target=play, args=(instrument, volume)).start()
                break
        if not found:
            print("{}: -".format(ip))
