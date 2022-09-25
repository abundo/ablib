#!/usr/bin/env python3
"""
Class to handle Oxidized
"""
# python standard modules

# modules installed with pip
import requests
from orderedattrdict import AttrDict

# my modules
import ablib.utils as abutils

# ----- Start of configuration items -----

CONFIG_FILE = "/etc/factum/factum.yaml"

# ----- End of configuration items -----


class OxidizedException(Exception):
    pass


class Oxidized_Mgr:

    exception = OxidizedException

    def __init__(self, config=None):
        self.config = config
        self.devices = None

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

    def get_device(self, name=None):
        raise OxidizedException("Not implemented")

    def get_devices(self):
        if not self.devices:
            self.load_devices()
            return self.devices
    
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
    
    def save_devices(self, filename, devices, ignore_models=None):
        """
        Write a new router.db for oxidized, with name:model for all devices
        """
        count = 0
        with open(filename, 'w') as f:
            for name, device in devices.items():
                if device.primary_ip4:
                    model = device.platform   # device-api 'platform' is called 'model' in oxidized
                    addr4 = device.primary_ip4.address.split("/")[0]
                    if name == addr4:
                        f.write(f"{addr4}:{model}\n")
                    else:
                        f.write(f"{name}:{model}\n")
                    count += 1
        return count

    def reload(self):
        """
        Ask oxidized to reload configuration file
        Returns True if ok
        """
        url = f"{self.config.url}/reload?format=json"
        r = requests.get(url)
        return r.status_code


def main():
    """
    Function tests
    """

    # Load configuration
    try:
        config = abutils.yaml_load(CONFIG_FILE)
    except abutils.UtilException as err:
        abutils.die("Cannot load configuration file, err: %s" % err)
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=[
        "get_device",
        "get_devices",
        "get_device_config",
        "reload",
    ])
    parser.add_argument("--router_db", default="/etc/oxidized/router.db")
    parser.add_argument("-n", "--name", default=None)
    args = parser.parse_args()

    oxidized_mgr = Oxidized_Mgr(config=config.oxidized)

    if args.cmd == 'get_device':
        if args.name is None:
            abutils.die("Must specify name")
        device = oxidized_mgr.get_device(name=args.name)
        print(device)

    elif args.cmd == 'get_devices':
        devices = oxidized_mgr.get_devices()
        for name, device in devices.items():
            print(name, device)
        print(f"Found {len(devices)} devices")

    elif args.cmd == "get_device_config":
        if args.name is None:
            abutils.die("Must specify name")
        conf = oxidized_mgr.get_device_config(args.name)
        print(conf)

    elif args.cmd == 'reload':
        oxidized_mgr.reload()

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
