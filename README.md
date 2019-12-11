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
Sounds can be created based on any Wireshark field. You can provide your own mapping of fields to notes, or use one of the default provided mappings `protocol`, `ip`, or `tcp`. 

### Instrument mapping
Notes are chosen baesd on a dictionary structured as:

```json
{trigger: [instrument, pitch, volume]}
```
where:
- **trigger**:     may be one of:
  - `<Wireshark protocol name>` eg "icmp"
  - `<Wireshark display field>` `<operator>` `<value>` eg "ip.addr == 8.8.8.8" 
- **instrument**:  string, use -l to list available [instruments](https://www.midi.org/specifications/item/gm-level-1-sound-set)
- **pitch**:       integer from 21-108, see https://newt.phys.unsw.edu.au/jw/notes.html for mapping to note names
- **volume**:      integer from 0-127

### Tempo
By default notes are played as soon as the packet is received. To align notes to a beat frequency use the `-b` flag, which can take an integer (eg `60` for 60 beats per minute), or a string which includes the beat frequency and the instrument to play, in the format:
```
"<frequency> '<instrument>' pitch volume"
```

If, during the beat interval, two or more identical notes are triggered then a single note will be played at a higher volume, increasing the volume by 2 for each matching note.


### Examples
Sonify traffic on *Ethernet* interface based on default protocols:
```
py .\sonnet.py -i Ethernet -s protocol
```
Fire a shot for an ICMP (ping) packet and play a trumpet for a TCP reset:
```
py .\sonnet.py -i Ethernet -m '{"icmp":["gunshot",50,80],"tcp.flags.reset==1":["trumpet",90,120]}'
```

Align notes to beat frequency of 60 beats per minute:
```
py .\sonnet.py -i Ethernet -s protocol -b 60
```
and add a drumbeat:
```
py .\sonnet.py -i Ethernet -s protocol -b "60 'bass drum 1' 50 40"
```

Sonify based on TCP conversations, add a drumbeat, and print each matching note:
```
py .\sonnet.py -i Ethernet -s tcp -b "60 'bass drum 1' 36 40" -v
```
[Listen and watch here](example-tcp.mp4)

### Windows quirks
In Windows CMD the dictionary needs to have triple quotes around strings, eg:
```
py .\sonnet.py -i Ethernet -v -m {"""icmp""":["""gunshot""",50,80],"""tcp.flags.reset==1""":["""open hi-hat""",90,120]}
```
In Windows PowerShell it additionally needs to be single-quoted, eg:
```
py .\sonnet.py -i Ethernet -v -m '{"""icmp""":["""gunshot""",50,80],"""tcp.flags.reset==1""":["""open hi-hat""",90,120]}'
```