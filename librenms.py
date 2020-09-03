#!/usr/bin/env python3
"""
Class to manage librenms
"""

# ----- Start of configuration items -----

CONFIG_FILE="/etc/abtools/abtools_librenms.yaml"

# ----- End of configuration items -----

import sys
import requests
from orderedattrdict import AttrDict

import ablib.utils as utils
from ablib.db import Database


class Librenms_Mgr:

    def __init__(self, config=None, load=True):
        self.config = config
        self.devices = None         # key is name, value is dict with key-val
        self.interfaces = None      # key is name, value is dict(key interface name, val is interface key-val)
        self.db = Database(self.config.db)

        if load:
            self.load_devices()

    def _format_name(self, name):
        if name.find('.') < 0:
            name = name + self.config.default_domain
        return name

    def load_devices(self):
        url = self.config.api.url + "/devices"
        headers = {'X-Auth-Token': self.config.api.key}
        r = requests.get(url=url, headers=headers)
        tmp_devices = r.json()
        
        self.devices = AttrDict()
        for device in tmp_devices['devices']:
            name = device['hostname'].lower()
            self.devices[name] = device

    def get_device(self, name=None):
        name = self._format_name(name)
        if name not in self.devices:
            return None
        return self.devices[name]

    def get_devices(self):
        return self.devices
    
    def create_device(self, name=None, force_add=0):
        name = self._format_name(name)

        url = self.config.api.url + "/devices"
        headers = {'X-Auth-Token': self.config.api.key}

        data = AttrDict()
        data.name = name
        data.version = self.config.snmp.version
        data.force_add = force_add

        try:
            r = requests.post(url=url, json=data, headers=headers)
            print(r.json())
        except requests.exceptions.HTTPError as err:
            print("Error adding device: %s" % err)
            
    def update_device(self, name=None, data=None):
        name = self._format_name(name)
        print("name...", name)
        url = self.config.api.url + "/devices/" + name
        headers = {'X-Auth-Token': self.config.api.key}
        d = AttrDict(field=[], data=[])
        
        for key,value in data.items():
            d.field.append(key)
            d.data.append(value)
        
        r = requests.patch(url, json=d, headers=headers)
        return r.json()

    def delete_device(self, name=None):
        name = self._format_name(name)

        url = self.config.api.url + "/devices/" + name
        headers = {'X-Auth-Token': self.config.api.key}
        try:
            r = requests.delete(url=url, headers=headers)
            print(r.json())
        except requests.exceptions.HTTPError as err:
            print("Error deleting device: %s" % err)

    def load_interfaces(self):
        """
        Load all librenms interfaces to memory
        load_devices() must be called before this method
        """
        url = self.config.api.url + "/ports?columns=port_id,device_id,ifName"
        headers = {'X-Auth-Token': self.config.api.key}
        r = requests.get(url=url, headers=headers)
        tmp_devices = r.json()
        #todo

    def get_device_interfaces(self, name=None, device_id=None):
        """
        Get all device port info 
        API does not support everything we need, so we read the database directly
        """
        if device_id is None:
            name = self._format_name(name)
            sql = "SELECT device_id FROM devices WHERE hostname=%s"
            row = self.db.select_one(sql, (name,))
            if row is None:
                return None
            device_id = row.device_id
        sql = "SELECT port_id,ifname,ifdescr,ifalias,`ignore` FROM ports WHERE device_id=%s"
        rows = self.db.select_all(sql, (device_id),)
        interfaces = AttrDict()
        for row in rows:
            name = row.ifname
            interface = AttrDict()
            interface.ifname = row.ifname
            interface.ifdescr = row.ifdescr
            interface.ifalias = row.ifalias
            interface.port_id = row.port_id
            interface.ignore = row.ignore
            interfaces[name] = interface
        return interfaces
        
    def update_device_interface(self, port_id=None, data=None):
        data.port_id = port_id
        self.db.update("ports", d=data, primary_key="port_id")


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
    parser.add_argument('--cmd', required=True, 
                        choices=['get_devices', 
                                 'create_device', 
                                 'delete_device',
                                 'get_interfaces',
                                 ])
    parser.add_argument('--name', default=None)
    args = parser.parse_args()

    librenms_mgr = Librenms_Mgr(config=config.librenms)
    cmd = args.cmd
    if cmd == 'get_devices':
        devices = librenms_mgr.get_devices()
        for name, device in devices.items():
            print(name, device)
            print()
        print("Librenms: %5d devices" % len(devices))

    elif cmd == 'create_device':
        if args.name is None:
            print("Missing name")
            sys.exit(1)
        librenms_mgr.create_device(name=args.name, force_add=1)

    elif cmd == 'delete_device':
        if args.name is None:
            print("Missing name")
            sys.exit(1)
        librenms_mgr.delete_device(name=args.name)

    elif cmd == 'get_interfaces':
        if args.name is None:
            print("Missing name")
            sys.exit(1)
        interfaces = librenms_mgr.get_device_interfaces(name=args.name)
        for interface in interfaces:
            print(interface)

    else:
        print("Unknown command %s" % cmd)

if __name__ == '__main__':
    main()
