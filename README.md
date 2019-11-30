# sonnet
Sonify network traffic

Sonnet will convert a network capture into sound, so that you can hear traffic on the network.

## Requirements
- Python3
- [pygame](https://www.pygame.org/) - install with ```pip3 install pygame```

## Usage
Pipe a network capture into sonnet and convert to sounds based on protocol:
```
"C:\Program Files\Wireshark\tshark.exe" -i WiFi -q -l -T fields -e frame.protocols -e ip.addr -e ipv6.addr | py .\sonnet.py -p
```
Sounds can be created based on protocol or IP address, and some defaults are included. You can also specify your own, see help for info.
