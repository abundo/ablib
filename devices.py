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
        self.verify = self.config.get("verify", True)
        self.devices = {}

    def __len__(self):
        return len(self.devices)

    def load_devices(self):
        self.devices = {}
        r = requests.get(url=self.config.url, verify=self.verify)
        self.devices = json.loads(r.text, object_pairs_hook=AttrDict)

    def get_device(self, name=None):
        if name in self.devices:
            return self.devices[name].values()
        r = requests.get(url=self.config.url + "/" + name, verify=self.verify)
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

    def write_etc_hosts(self, devices=None):
        """
        Update /etc/hosts file with all devices primary_ipv4, from device-api
        Note: If you change the delemiter, you need to manually cleanup the hosts file
        """
        delemiter = "# ----- do not edit below - updated by a script -----"
        if devices is None:
            devices = self.devices
        if not devices:
            raise DeviceException("Error: Cannot update /etc/hosts with zero devices")
        with open("/etc/hosts", "r+") as f:
            line = f.readline()
            while line:
                line = line.strip()
                if line == delemiter:
                    print("  Delemiter found, writing %d entries." % len(devices))
                    f.seek(f.tell())
                    for hostname, device in devices.items():
                        primary_ip4 = device.get("primary_ip4", None)
                        # primary_ip6 = device.get("primary_ip6", None)
                        if primary_ip4:
                            addr4 = primary_ip4.address.split("/")[0]
                            if addr4 != hostname:
                                # short_hostname = hostname
                                tmp = "%-18s %s" % (addr4, hostname)
                                p = hostname.find(".")
                                if p >= 0:
                                    tmp += "  %s" % hostname[:p]
                                f.write("%s\n" % tmp)
                    f.write("# ----- end -----\n")
                    f.truncate()
                    return
                line = f.readline()


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
        "write_etc_hosts",
    ])
    parser.add_argument("-n-", "--name", default=None)
    args = parser.parse_args()

    config = abutils.load_config(CONFIG_FILE)

    device_mgr = Device_Mgr(config=config.device)

    if args.cmd == "get_device":
        device = device_mgr.get_device(name=args.name)
        print(device)

    elif args.cmd == "get_devices":
        devices = device_mgr.get_devices()
        for name, device in devices.items():
            print(name, device)
        print("Devices: %5d devices" % len(devices))

    elif args.cmd == "get_device_interfaces":
        interfaces = device_mgr.get_device_interfaces(name=args.name)
        print(interfaces)

    elif args.cmd == "write_etc_hosts":
        devices = device_mgr.get_devices()
        device_mgr.write_etc_hosts()

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
