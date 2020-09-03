#!/usr/bin/env python3
"""
Class to handle Oxidized
"""

# ----- Start of configuration items -----

CONFIG_FILE="/etc/abtools/abtools_oxidized.yaml"

# ----- End of configuration items -----

import sys
import subprocess
import requests
from orderedattrdict import AttrDict

import ablib.utils as utils

class Oxidized_Mgr:

    def __init__(self, config=None, load=False):
        self.config = config
        self.devices = None
        if load:
            self.load_devices()

    def __len__(self):
        return len(self.devices)

    def load_devices(self):
        self.devices = AttrDict()
        with open(self.config.router_db.dst, 'r') as f:
            for line in f.readlines():
                tmp = line.strip().split(":")
                if len(tmp) < 2:
                    print("Ignoring line ", line)
                    continue
                device = AttrDict()
                device.name = tmp[0]
                device.model = tmp[1]
                self.devices[device.name] = device

    def get_devices(self):
        return self.devices
    
    def get_device_interfaces(self, name):
        return None
    
    def get_device_config(self, name):
        """
        Fetch last device configuration
        If no configuration found, return None
        """
        url = self.config.url + "/node/fetch/%s" % name
        if "username" in self.config:
            r = requests.get(url, auth=requests.auth.HTTPBasicAuth(self.config.username, self.config.password))
        else:
            r = requests.get(url)
        if r.status_code == 200:
            return r.text
        return None
    
    def save_devices(self, filename, devices, ignore_models = None):
        if ignore_models is None:
            ignore_models = {}
        count = 0
        with open(filename, 'w') as f:
            for name, device in devices.items():
                # Device API is 'platform' oxidized calls it 'model'
                if 'platform' in device:
                    model = device['platform']
                    if model and model not in ignore_models:
                        if name == device['ipv4_addr']:
                            f.write("%s:%s\n" % (device['ipv4_addr'], model))
                        else:
                            f.write("%s:%s\n" % (device['name'], model))
                        count += 1
                else:
                    print("backup_oxidized is False for %s" % name)
        return count

    def reload(self):
        """
        Reload configuration file
        Returns True if ok
        """
        url = "%s/reload?format=json" % self.config.url
        r = requests.get(url)
        return print(r.status_code)


def main():
    """
    Function tests
    """

    # Load configuration
    try:
        config = utils.yaml_load(CONFIG_FILE)
    except utils.UtilException as err:
        utils.die("Cannot load configuration file, err: %s" % err)
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, 
                        choices=["get_devices", 
                                 "get_device_config",
                                 "reload",
                                 ])
    parser.add_argument("--router_db", default="/etc/oxidized/router.db")
    parser.add_argument("-H", "--name", default=None)
    args = parser.parse_args()

    oxidized_mgr = Oxidized_Mgr(config=config.oxidized)

    if args.cmd == 'get_devices':
        oxidized_mgr.load_devices()
        device_list = oxidized_mgr.get_devices()
        for name, device in device_list.items():
            print(name, device)
        print("Devices: %5d devices" % len(device_list))

    elif args.cmd == "get_device_config":
        if args.name is None:
            utils.die("Must specify name")
        conf = oxidized_mgr.get_device_config(args.name)
        print(conf)

    elif args.cmd == 'reload':
        oxidized_mgr.reload()

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
