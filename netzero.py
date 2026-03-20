import subprocess

from threading import Thread, Event

from scapy.layers.dot11 import Dot11Beacon
from scapy.packet import Packet
from scapy.all import sniff

from utils import get_wifi_interfaces, channel_hopper, is_packet_dot11, get_bssid, parse_ssid, parse_crypto, get_rssi



class NetZero:
    def __init__(self, status_callback, data_callback):  # status callback (interface, monitor mode, channel etc.), data callback (scanned networks, clients etc.)
        self.set_status = status_callback
        self.add_data = data_callback
        self.interface = 'wlan0'  # make selection for this
        self.networks = {}

        self.current_task = 'idle'
        self.stop_flag = Event()

    def get_current_task(self):
        return self.current_task
    
    def is_current_task(self, task):
        return self.current_task == task
    
    def is_idle(self):
        return self.is_current_task('idle')
    
    def set_current_task(self, task):
        self.current_task = task

    def stop_current_task(self):
        self.set_status('Stopping...')
        self.stop_flag.set()
        self.set_current_task('idle')

    def get_interface(self):
        return self.interface

    def get_interfaces(self):
        return get_wifi_interfaces()

    def enable_monitor_mode(self):
        self.set_status(f'Entering monitor mode...')
        mon_interface = self.interface + 'mon'

        # subprocess.run(['systemctl', 'stop', 'NetworkManager'])
        # subprocess.run(['systemctl', 'stop', 'wpa_supplicant'])
        subprocess.run(['nmcli', 'device', 'set', self.interface, 'managed', 'no'])
        subprocess.run(['ip', 'link', 'set', self.interface, 'down'])
        subprocess.run(['iw', 'dev', self.interface, 'interface', 'add', mon_interface, 'type', 'monitor'])
        subprocess.run(['ip', 'link', 'set', mon_interface, 'up'])

        self.interface = mon_interface
        self.set_status(f'Monitor mode enabled.')

    def disable_monitor_mode(self):
        self.set_status(f'Disabling monitor mode...')
        managed_interface = self.interface[:-3]

        subprocess.run(['ip', 'link', 'set', self.interface, 'down'])
        subprocess.run(['iw', 'dev', self.interface, 'del'])
        subprocess.run(['ip', 'link', 'set', managed_interface, 'up'])
        subprocess.run(['nmcli', 'device', 'set', managed_interface, 'managed', 'yes'])

        self.interface = managed_interface
        self.set_status(f'Monitor mode disabled.')

    def is_monitor_mode(self):
        return self.interface[-3:] == 'mon'

    def ensure_monitor_mode(self):
        if not self.is_monitor_mode():
            self.enable_monitor_mode()

    def network_scan_packet_handler(self, packet: Packet):
        if not is_packet_dot11(packet):
            return

        bssid = get_bssid(packet)
        if bssid in self.networks:
            return
        
        stats = packet[Dot11Beacon].network_stats()
        
        ssid, channel, rates = parse_ssid(stats['ssid']), stats['channel'], stats['rates']
        crypto, rssi = parse_crypto(stats['crypto']), get_rssi(packet)

        self.networks[bssid] = {
            'ssid': ssid, 
            'pwr': rssi, 
            'channel': channel, 
            'crypto': crypto, 
        }

        row_num = len(self.networks)
        self.add_data(f'{row_num:<3} | {bssid:<17} | {rssi:<4} | {channel:<3} | {crypto:<10} | {ssid[:25]}')

    def network_scanner_task(self):
        self.set_status('Initializing network scan...')
        self.ensure_monitor_mode()
        self.stop_flag.clear()
        self.networks = {}

        def is_stopped(packet):
            return self.stop_flag.is_set()

        with channel_hopper(self.interface, delay=0.5):
            self.set_current_task('scanning')
            self.set_status('Scanning for networks on all channels...')
            sniff(
                iface=self.interface,
                prn=self.network_scan_packet_handler, 
                store=False,
                stop_filter=is_stopped
            )

        self.set_status('Network scan concluded.')
        self.disable_monitor_mode()
        self.set_current_task('idle')

    def scan_networks(self):
        scan_thread = Thread(
            target=self.network_scanner_task,
            daemon=True
        )
        scan_thread.start()
        

    