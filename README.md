# Sonnet
Sonnet will sonify a network capture - turning packets into sound - so that you can hear your network.

## Requirements
- Python3
- [pygame](https://www.pygame.org/)

## Installation
```
pip3 install pygame
git clone https://github.com/gaddman/sonnet.git
```

## Usage
Sounds can be created based on any Wireshark field. You can provide your own mapping of fields to notes, or use one of the default provided mappings `protocol` or `ip`.

### Examples
Sonify traffic on *Ethernet* interface based on default protocols:
```
py .\sonnet.py -i Ethernet -s protocol
```
Fire a shot for an ICMP (ping) packet and play a trumpet for a TCP reset:
```
py .\sonnet.py -i Ethernet -m '{"icmp":["gunshot",50,80],"tcp.flags.reset==1":["trumpet",90,120]}'
```
The instrument mapping is a dictionary:

- **Trigger**:     in the format `<Wireshark display field>` `<operator>` `<value>`, eg "ip.addr == 8.8.8.8" or a protocol, eg "icmp"
- **Instrument**:  string, use -l to list available [instruments](https://www.midi.org/specifications/item/gm-level-1-sound-set)
- **Pitch**:       integer from 21-108, see https://newt.phys.unsw.edu.au/jw/notes.html for mapping to note names
- **Volume**:      integer from 0-127


In Windows the dictionary needs to have quotes escaped and spaces quoted, eg from CMD:
```
py .\sonnet.py -i Ethernet -v -m {\"icmp\":[\"gunshot\",50,80],\"tcp.flags.reset==1\":[\""open hi-hat"\",90,120]}
```
