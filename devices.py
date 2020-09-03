#!/usr/bin/env python3
"""
Class to handle devices, using Device API
"""

import sys
import requests


class Device_Mgr:
    def __init__(self, config=None):
        self.config = config
        self.devices = {}
        self._loaded = False

    def __len__(self):
        return len(self.devices)

    def load_devices(self):
        self.devices = {}
        r = requests.get(url=self.config["api"]["url"])
        self.devices = r.json()

    def get_device(self, name):
        if name in self.devices:
            return self.devices[name]
        r = requests.get(url=self.config["api"]["url"] + "/" + name)
        device = r.json()
        name = list(device.keys())[0]
        self.devices[name] = device
        return device

    def get_devices(self):
        if not self._loaded:
            self._loaded = True
            self.load_devices()
        return self.devices
    
    def get_device_interfaces(self, name):
        if name in self.devices:
            return self.devices[name]['interfaces']
        return None
    

def main():
    """
    Function tests
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cmd', required=True, 
                        choices=['get_devices', 
                                 ])
    parser.add_argument('--name', default=None)
    parser.add_argument("--api_url", required=True, default=None)
    args = parser.parse_args()

    # Create a dummy config
    config = {}
    config["api"] = {}
    config["api"]["url"] = args.api_url

    device_mgr = Device_Mgr(config=config)

    if args.cmd == 'get_devices':
        devices = device_mgr.get_devices()
        for name, device in devices.items():
            print(name, device)
        print("Devices: %5d devices" % len(devices))
    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
