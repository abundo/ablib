#!/usr/bin/env python3
"""
Class to handle devices, using device-api
"""

# python standard modules
import json

# modules installed with pip
import requests
from orderedattrdict import AttrDict

# my modules
import ablib.utils as abutils


# ----- Start of configuration items ----------------------------------------

CONFIG_FILE = "/etc/abcontrol/abcontrol.yaml"

# ----- End of configuration items ------------------------------------------


class DeviceException(Exception):
    pass


class Device_Mgr:

    exception = DeviceException

    def __init__(self, config=None):
        self.config = config
        self.devices = {}

    def __len__(self):
        return len(self.devices)

    def load_devices(self):
        self.devices = {}
        r = requests.get(url=self.config.devices.api.url)
        self.devices = json.loads(r.text, object_pairs_hook=AttrDict)

    def get_device(self, name=None):
        if name in self.devices:
            return self.devices[name].values()
        r = requests.get(url=self.config.devices.api.url + "/" + name)
        device = json.loads(r.text, object_pairs_hook=AttrDict)
        for d in device.values():
            return d

    def get_devices(self):
        if not self.devices:
            self.load_devices()
        return self.devices
    
    def get_device_interfaces(self, name=None):
        device = self.get_device(name=name)
        if device:
            return device.interfaces
        return None


def main():
    """
    Function tests
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=[
        "get_devices",
        "get_device",
        "get_device_interfaces",
    ])
    parser.add_argument("-n-", "--name", default=None)
    args = parser.parse_args()

    config = abutils.load_config(CONFIG_FILE)

    device_mgr = Device_Mgr(config=config)

    if args.cmd == 'get_device':
        device = device_mgr.get_device(name=args.name)
        print(device)

    elif args.cmd == 'get_devices':
        devices = device_mgr.get_devices()
        for name, device in devices.items():
            print(name, device)
        print("Devices: %5d devices" % len(devices))

    elif args.cmd == "get_device_interfaces":
        interfaces = device_mgr.get_device_interfaces(name=args.name)
        print(interfaces)

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
