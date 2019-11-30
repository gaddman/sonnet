#! python3.7
# Using python3.7 on Windows because pygame.midi doesn't work on 3.8

# Sonify a Wireshark capture
#
# Expecting Tshark format "frame.protocols", eg start with:
# Windows Command:
#   "C:\Program Files\Wireshark\tshark.exe" -i Ethernet -Q -l -T tabs -T fields -e "frame.protocols" | py .\dundun.py
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


# Instrument and Percussion map from
# https://www.midi.org/specifications/item/gm-level-1-sound-set

instruments = {
    "acoustic grand piano": 1,
    "bright acoustic piano": 2,
    "electric grand piano": 3,
    "honky-tonk piano": 4,
    "electric piano 1": 5,
    "electric piano 2": 6,
    "harpsichord": 7,
    "clavi": 8,
    "celesta": 9,
    "glockenspiel": 10,
    "music box": 11,
    "vibraphone": 12,
    "marimba": 13,
    "xylophone": 14,
    "tubular bells": 15,
    "dulcimer": 16,
    "drawbar organ": 17,
    "percussive organ": 18,
    "rock organ": 19,
    "church organ": 20,
    "reed organ": 21,
    "accordion": 22,
    "harmonica": 23,
    "tango accordion": 24,
    "acoustic guitar (nylon)": 25,
    "acoustic guitar (steel)": 26,
    "electric guitar (jazz)": 27,
    "electric guitar (clean)": 28,
    "electric guitar (muted)": 29,
    "overdriven guitar": 30,
    "distortion guitar": 31,
    "guitar harmonics": 32,
    "acoustic bass": 33,
    "electric bass (finger)": 34,
    "electric bass (pick)": 35,
    "fretless bass": 36,
    "slap bass 1": 37,
    "slap bass 2": 38,
    "synth bass 1": 39,
    "synth bass 2": 40,
    "violin": 41,
    "viola": 42,
    "cello": 43,
    "contrabass": 44,
    "tremolo strings": 45,
    "pizzicato strings": 46,
    "orchestral harp": 47,
    "timpani": 48,
    "string ensemble 1": 49,
    "string ensemble 2": 50,
    "synthstrings 1": 51,
    "synthstrings 2": 52,
    "choir aahs": 53,
    "voice oohs": 54,
    "synth voice": 55,
    "orchestra hit": 56,
    "trumpet": 57,
    "trombone": 58,
    "tuba": 59,
    "muted trumpet": 60,
    "french horn": 61,
    "brass section": 62,
    "synthbrass 1": 63,
    "synthbrass 2": 64,
    "soprano sax": 65,
    "alto sax": 66,
    "tenor sax": 67,
    "baritone sax": 68,
    "oboe": 69,
    "english horn": 70,
    "bassoon": 71,
    "clarinet": 72,
    "piccolo": 73,
    "flute": 74,
    "recorder": 75,
    "pan flute": 76,
    "blown bottle": 77,
    "shakuhachi": 78,
    "whistle": 79,
    "ocarina": 80,
    "lead 1 (square)": 81,
    "lead 2 (sawtooth)": 82,
    "lead 3 (calliope)": 83,
    "lead 4 (chiff)": 84,
    "lead 5 (charang)": 85,
    "lead 6 (voice)": 86,
    "lead 7 (fifths)": 87,
    "lead 8 (bass + lead)": 88,
    "pad 1 (new age)": 89,
    "pad 2 (warm)": 90,
    "pad 3 (polysynth)": 91,
    "pad 4 (choir)": 92,
    "pad 5 (bowed)": 93,
    "pad 6 (metallic)": 94,
    "pad 7 (halo)": 95,
    "pad 8 (sweep)": 96,
    "fx 1 (rain)": 97,
    "fx 2 (soundtrack)": 98,
    "fx 3 (crystal)": 99,
    "fx 4 (atmosphere)": 100,
    "fx 5 (brightness)": 101,
    "fx 6 (goblins)": 102,
    "fx 7 (echoes)": 103,
    "fx 8 (sci-fi)": 104,
    "sitar": 105,
    "banjo": 106,
    "shamisen": 107,
    "koto": 108,
    "kalimba": 109,
    "bag pipe": 110,
    "fiddle": 111,
    "shanai": 112,
    "tinkle bell": 113,
    "agogo": 114,
    "steel drums": 115,
    "woodblock": 116,
    "taiko drum": 117,
    "melodic tom": 118,
    "synth drum": 119,
    "reverse cymbal": 120,
    "guitar fret noise": 121,
    "breath noise": 122,
    "seashore": 123,
    "bird tweet": 124,
    "telephone ring": 125,
    "helicopter": 126,
    "applause": 127,
    "gunshot": 128,
}

percussion = {
    "acoustic bass drum": 35,
    "bass drum 1": 36,
    "side stick": 37,
    "acoustic snare": 38,
    "hand clap": 39,
    "electric snare": 40,
    "low floor tom": 41,
    "closed hi hat": 42,
    "high floor tom": 43,
    "pedal hi-hat": 44,
    "low tom": 45,
    "open hi-hat": 46,
    "low-mid tom": 47,
    "hi-mid tom": 48,
    "crash cymbal 1": 49,
    "high tom": 50,
    "ride cymbal 1": 51,
    "chinese cymbal": 52,
    "ride bell": 53,
    "tambourine": 54,
    "splash cymbal": 55,
    "cowbell": 56,
    "crash cymbal 2": 57,
    "vibraslap": 58,
    "ride cymbal 2": 59,
    "hi bongo": 60,
    "low bongo": 61,
    "mute hi conga": 62,
    "open hi conga": 63,
    "low conga": 64,
    "high timbale": 65,
    "low timbale": 66,
    "high agogo": 67,
    "low agogo": 68,
    "cabasa": 69,
    "maracas": 70,
    "short whistle": 71,
    "long whistle": 72,
    "short guiro": 73,
    "long guiro": 74,
    "claves": 75,
    "hi wood block": 76,
    "low wood block": 77,
    "mute cuica": 78,
    "open cuica": 79,
    "mute triangle": 80,
    "open triangle": 81,
}

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
    print(list(instruments.keys()))
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


def signal_handler(signal, frame):
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
    if instrument in instruments:
        instrument_type = "melodic"
        instrumentnum = instruments[instrument] - 1
        pitch = 72
        channel = 0
        midiOut.set_instrument(instrumentnum, channel)
    else:
        instrument_type = "percussion"
        instrumentnum = percussion[instrument]
        pitch = instrumentnum
        channel = 9

    midiOut.note_on(pitch, volume, channel)
    sleep(0.5)
    midiOut.note_off(pitch, volume, channel)


# Handle Ctrl-C press
signal.signal(signal.SIGINT, signal_handler)

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
