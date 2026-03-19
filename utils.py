import subprocess

from contextlib import contextmanager
from threading import Thread, Event

from scapy.layers.dot11 import Dot11, Dot11Beacon, RadioTap
from scapy.packet import Packet

CHANNELS_2GHz = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


def get_wifi_interfaces():
    interfaces = []
    result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, check=True)
        
    for line in result.stdout.split('\n'):
        if "Interface" in line:
            interface = line.split()[1]
            interfaces.append(interface)
        
    return interfaces


def set_channel(interface, channel):
    subprocess.run(
        ['iw', 'dev', interface, 'set', 'channel', str(channel)],
        stderr=subprocess.DEVNULL
    )

# only run as Thread
def hop_channels(interface, delay, stop_event: Event):
    while not stop_event.is_set():
        for channel in CHANNELS_2GHz:
            set_channel(interface, channel)
            stopped = stop_event.wait(timeout=delay)
            if stopped:
                return
            
@contextmanager
def channel_hopper(interface, delay):
    stop_event = Event()

    hopper_thread = Thread(
        target=hop_channels,
        args=(interface, delay, stop_event),
        daemon=True)
    
    hopper_thread.start()

    try:
        yield hopper_thread

    finally:
        stop_event.set()
        hopper_thread.join()

def is_packet_dot11(packet: Packet):
    return packet.haslayer(Dot11Beacon)

def get_bssid(packet: Packet):
    return packet[Dot11].addr3

def get_rssi(packet: Packet):
    rssi = -100

    # todo: wtf
    if packet.haslayer(RadioTap) and hasattr(packet[RadioTap], 'dBm_AntSignal') and packet[RadioTap].dBm_AntSignal is not None:
        rssi = int(packet[RadioTap].dBm_AntSignal)

    return rssi

def parse_crypto(crypto):
    simplified = set()
    
    for c in crypto:
        if c.startswith('WPA3-transition'):
            simplified.update(['WPA2', 'WPA3'])
        else:
            base_protocol = c.split('/')[0]
            simplified.add(base_protocol)
            
    order = {'OPN': 0, 'WEP': 1, 'WPA': 2, 'WPA2': 3, 'WPA3': 4}
    sorted_crypto = sorted(list(simplified), key=lambda x: order.get(x, 99))
    
    return '/'.join(sorted_crypto)

def parse_ssid(raw_ssid):
    ssid = ''.join(c for c in raw_ssid if c.isprintable()).strip()
    if not ssid:
        ssid = '<Hidden>'
    return ssid
