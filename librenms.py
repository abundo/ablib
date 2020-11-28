#!/usr/bin/env python3
"""
Class to manage librenms
"""
import json
import requests

# modules installed with pip
from orderedattrdict import AttrDict

# my modules
import ablib.utils as abutils
from ablib.db import Database

# ----- Start of configuration items -----

CONFIG_FILE = "/etc/abcontrol/abcontrol.yaml"

# ----- End of configuration items -----


class LibrenmsException(Exception):
    pass


class Librenms_Mgr:

    exception = LibrenmsException

    def __init__(self, config=None):
        self.config = config
        self.db = Database(self.config.librenms.db)
        self.clear_cache()

    def call_api(self, method=None, endpoint=None, data=None):
        """
        Helper, to setup headers etc for calling Librenms API
        Caller needs to handle exceptions
        """
        url = self.config.librenms.api.url + endpoint
        headers = {'X-Auth-Token': self.config.librenms.api.key}
        if method == "DELETE":
            r = requests.delete(url=url, headers=headers)
        elif method == "POST":
            r = requests.post(url=url, headers=headers, json=data)
        elif method == "PATCH":
            r = requests.patch(url, headers=headers, json=data)
        else:
            # Default GET
            r = requests.get(url=url, headers=headers)
        return r

    def _load_devices(self):
        """
        Load all librenms devices into memory
        """
        self.clear_cache()
        if self.devices:
            return
        try:
            r = self.call_api(endpoint="/devices")
            tmp_devices = json.loads(r.text, object_pairs_hook=AttrDict)
            
            self.devices = AttrDict()
            for device in tmp_devices.devices:
                name = device.hostname.lower()
                self.devices[name] = device
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException("Cannot load librenms devices into memory: %s" % err)

    def _load_interfaces(self):
        """
        Load all librenms interfaces to memory
        """
        self._load_devices()
        try:
            r = self.call_api(endpoint="/ports?columns=port_id,device_id,ifName")
            self.interfaces = json.loads(r.text, object_pairs_hook=AttrDict)
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException("Cannot load librenms interfaces into memory: %s" % err)

    def _load_locations(self):
        """
        Load all librenms locations into memory
        """
        try:
            r = self.call_api(endpoint="/ports?columns=port_id,device_id,ifName")
            # r = requests.get(url=url, headers=headers)
            self.locations = json.loads(r.text, object_pairs_hook=AttrDict)
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException("Cannot load librenms interfaces into memory: %s" % err)

    def clear_cache(self):
        """
        Remove entries in cache, forcing reload when needed
        """
        self.devices = AttrDict()
        self.interfaces = AttrDict()

    def _format_name(self, name):
        if name.find('.') < 0:
            name = name + "." + self.config.default_domain
        return name

    def get_device(self, name=None):
        self._load_devices()
        name = self._format_name(name)
        try:
            return self.devices[name]
        except TypeError:
            raise LibrenmsException(f"Unknown device with name {name}")

    def get_devices(self):
        self._load_devices()
        return self.devices
    
    def create_device(self, name=None, force_add=0):
        name = self._format_name(name)
        data = AttrDict()
        data.hostname = name
        data.version = self.config.librenms.snmp.version
        data.force_add = force_add

        try:
            r = self.call_api(method="POST", endpoint="/devices", data=data)
            self.clear_cache()
            return r.json()
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException(f"Error adding device {name}: {err}")
            
    def update_device(self, name=None, data=None):
        name = self._format_name(name)
        d = AttrDict(field=[], data=[])
        for key, value in data.items():
            d.field.append(key)
            d.data.append(value)
        try:
            r = self.call_api(method="PATCH", endpoint=f"/devices/{name}", data=d)
            self.clear_cache()
            return r.json()
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException(f"Error updating device {name}: {err}")

    def delete_device(self, name=None):
        name = self._format_name(name)
        try:
            r = self.call_api(method="DELETE", endpoint=f"/devices/{name}")
            self.clear_cache()
            return r.json()
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException(f"Error deleting device {name}: {err}")

    def set_device_parent(self, device_id=None, parent=None):
        """
        Set parents on a device
        parent is a list, each entry is one parent name
        """
        parent_ids = []
        for parent_name in parent:
            parent_name = self._format_name(parent_name)
            parent_data = self.devices[parent_name]
            parent_ids.append(str(parent_data["device_id"]))
        data = AttrDict(parent_ids=",".join(parent_ids))
        try:
            r = self.call_api(method="POST", endpoint=f"/devices/{device_id}/parents", data=data)
            # todo update cache
            return r
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException(f"Error setting parents on device_id {device_id}: {err}")

    def delete_device_parent(self, device_id=None, parent=None):
        """
        Remove a parent from a device
        parent is a list, each entry is one parent name
        """
        parent_ids = []
        for parent_name in parent:
            parent_name = self._format_name(parent_name)
            parent_data = self.devices[parent_name]
            parent_ids.append(str(parent_data["device_id"]))
        data = AttrDict()
        if len(parent_ids):
            data.parent_ids = ",".join(parent_ids)
        else:
            data = None
        try:
            r = self.call_api(method="POST", endpoint=f"/devices/{device_id}/parents", data=data)
            # todo update cache
            return r.json()
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException(f"Error deleting parents on device_id {device_id}: {err}")

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
        """
        """
        data.port_id = port_id
        self.db.update("ports", d=data, primary_key="port_id")

    def get_locations(self):
        """
        No API, read from database
        """
        sql = "SELECT * FROM locations"
        self.locations = self.db.select_all(sql)
        return self.locations


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
    parser.add_argument('cmd', choices=[
        "get_device",
        "get_devices",
        "create_device",
        "delete_device",
        "get_device_interfaces",
        "set_device_parent",
        "delete_device_parent",
        "get_locations",
    ])
    parser.add_argument("-n", "--name", default=None)
    parser.add_argument("--parent", default=[], action="append")
    parser.add_argument("--pretty", default=False, action="store_true")
    args = parser.parse_args()
    cmd = args.cmd

    librenms_mgr = Librenms_Mgr(config=config)

    if cmd == "get_device":
        if not args.name:
            abutils.die("Name is required")
        data = librenms_mgr.get_device(name=args.name)
        abutils.pprint(data)

    elif cmd == "get_devices":
        data = librenms_mgr.get_devices()
        abutils.pprint(data)

    elif cmd == "create_device":
        if not args.name:
            abutils.die("Name is required")
        data = librenms_mgr.create_device(name=args.name, force_add=1)
        abutils.pprint(data)

    elif cmd == "delete_device":
        if not args.name:
            abutils.die("Name is required")
        data = librenms_mgr.delete_device(name=args.name)
        abutils.pprint(data)

    elif cmd == "get_device_interfaces":
        if not args.name:
            abutils.die("Name is required")
        data = librenms_mgr.get_device_interfaces(name=args.name)
        abutils.pprint(data)

    elif cmd == "set_device_parent":
        if not args.name:
            abutils.die("Name is required")
        if not args.parent:
            abutils.die("Parent is required")
        device = librenms_mgr.get_device(name=args.name)
        data = librenms_mgr.set_device_parent(device_id=device["device_id"], parent=args.parent)
        abutils.pprint(data)

    elif cmd == "delete_device_parent":
        if not args.name:
            abutils.die("Name is required")
        if not args.parent:
            abutils.die("Parent is required")
        device = librenms_mgr.get_device(name=args.name)
        data = librenms_mgr.delete_device_parent(device_id=device["device_id"], parent=args.parent)
        abutils.pprint(data)

    elif cmd == "get_locations":
        locations = librenms_mgr.get_locations()
        abutils.pprint(locations)

    else:
        abutils.die(f"Unknown command {cmd}")


if __name__ == '__main__':
    main()
