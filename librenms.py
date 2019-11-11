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
        self.elements = None        # key is hostname, value is dict with key-val
        self.interfaces = None      # key is hostname, value is dict(key interface name, val is interface key-val)
        self.db = Database(self.config.db)

        if load:
            self.load_elements()

    def _format_hostname(self, hostname):
        if hostname.find('.') < 0:
            hostname = hostname + self.config.default_domain
        return hostname

    def load_elements(self):
        url = self.config.api.url + "/devices"
        headers = {'X-Auth-Token': self.config.api.key}
        r = requests.get(url=url, headers=headers)
        tmp_elements = r.json()
        
        self.elements = AttrDict()
        for element in tmp_elements['devices']:
            hostname = element['hostname'].lower()
            self.elements[hostname] = element

    def get_element(self, hostname=None):
        hostname = self._format_hostname(hostname)
        if hostname not in self.elements:
            return None
        return self.elements[hostname]

    def get_elements(self):
        return self.elements
    
    def create_element(self, hostname=None, force_add=0):
        hostname = self._format_hostname(hostname)

        url = self.config.api.url + "/devices"
        headers = {'X-Auth-Token': self.config.api.key}

        data = AttrDict()
        data.hostname = hostname
        data.version = self.config.snmp.version
        data.force_add = force_add

        try:
            r = requests.post(url=url, json=data, headers=headers)
            print(r.json())
        except requests.exceptions.HTTPError as err:
            print("Error adding element: %s" % err)
            
    def update_element(self, hostname=None, data=None):
        hostname = self._format_hostname(hostname)
        print("hostname...", hostname)
        url = self.config.api.url + "/devices/" + hostname
        headers = {'X-Auth-Token': self.config.api.key}
        d = AttrDict(field=[], data=[])
        
        for key,value in data.items():
            d.field.append(key)
            d.data.append(value)
        
        r = requests.patch(url, json=d, headers=headers)
        return r.json()

    def delete_element(self, hostname=None):
        hostname = self._format_hostname(hostname)

        url = self.config.api.url + "/devices/" + hostname
        headers = {'X-Auth-Token': self.config.api.key}
        try:
            r = requests.delete(url=url, headers=headers)
            print(r.json())
        except requests.exceptions.HTTPError as err:
            print("Error deleting element: %s" % err)

    def load_interfaces(self):
        """
        Load all librenms interfaces to memory
        load_elements() must be called before this method
        """
        url = self.config.api.url + "/ports?columns=port_id,device_id,ifName"
        headers = {'X-Auth-Token': self.config.api.key}
        r = requests.get(url=url, headers=headers)
        tmp_elements = r.json()
        #todo

    def get_element_interfaces(self, hostname=None, device_id=None):
        """
        Get all device port info 
        API does not support everything we need, so we read the database directly
        """
        if device_id is None:
            hostname = self._format_hostname(hostname)
            sql = "SELECT device_id FROM devices WHERE hostname=%s"
            row = self.db.select_one(sql, (hostname,))
            if row is None:
                return None
            device_id = row.device_id
        sql = "SELECT port_id,ifname,`ignore` FROM ports WHERE device_id=%s"
        rows = self.db.select_all(sql, (device_id),)
        interfaces = AttrDict()
        for row in rows:
            name = row.ifname
            interface = AttrDict()
            interface.port_id = row.port_id
            interface.ignore = row.ignore
            interfaces[name] = interface
        return interfaces
        
    def update_element_interface(self, port_id=None, data=None):
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
                        choices=['get_elements', 
                                 'create_element', 
                                 'delete_element',
                                 'get_interfaces',
                                 ])
    parser.add_argument('--hostname', default=None)
    args = parser.parse_args()

    librenms_mgr = Librenms_Mgr(config=config.librenms)
    cmd = args.cmd
    if cmd == 'get_elements':
        elements = librenms_mgr.get_elements()
        for hostname, element in elements.items():
            print(hostname, element)
            print()
        print("Librenms: %5d elements" % len(elements))

    elif cmd == 'create_element':
        if args.hostname is None:
            print("Missing hostname")
            sys.exit(1)
        librenms_mgr.create_element(hostname=args.hostname, force_add=1)

    elif cmd == 'delete_element':
        if args.hostname is None:
            print("Missing hostname")
            sys.exit(1)
        librenms_mgr.delete_element(hostname=args.hostname)

    elif cmd == 'get_interfaces':
        if args.hostname is None:
            print("Missing hostname")
            sys.exit(1)
        interfaces = librenms_mgr.get_element_interfaces(hostname=args.hostname)
        for interface in interfaces:
            print(interface)

    else:
        print("Unknown command %s" % cmd)

if __name__ == '__main__':
    main()
