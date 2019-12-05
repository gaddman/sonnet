# Sonnet
Sonnet will sonify a network capture - turning packets into sound - so that you can hear your network.

## Requirements
- Python3
- [pygame](https://www.pygame.org/)
- [TShark](https://www.wireshark.org/)

## Installation
Install pygame to provide MIDI output. In Ubuntu:
```
sudo apt install python3-pygame
```
or with PIP:
```
pip3 install pygame
```
And clone this repository:
```
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
The instrument mapping is a dictionary structured as:
`{trigger: [instrument, pitch, volume]}`

- **trigger**:     may be one of:
  - `<Wireshark protocol name>` eg "icmp"
  - `<Wireshark display field>` `<operator>` `<value>` eg "ip.addr == 8.8.8.8" 
- **instrument**:  string, use -l to list available [instruments](https://www.midi.org/specifications/item/gm-level-1-sound-set)
- **pitch**:       integer from 21-108, see https://newt.phys.unsw.edu.au/jw/notes.html for mapping to note names
- **volume**:      integer from 0-127

### Windows quirks
In Windows CMD the dictionary needs to have triple quotes around strings, eg:
```
py .\sonnet.py -i Ethernet -v -m {"""icmp""":["""gunshot""",50,80],"""tcp.flags.reset==1""":["""open hi-hat""",90,120]}
```
In Windows PowerShell it additionally needs to be single-quoted, eg:
```
py .\sonnet.py -i Ethernet -v -m '{"""icmp""":["""gunshot""",50,80],"""tcp.flags.reset==1""":["""open hi-hat""",90,120]}'
```