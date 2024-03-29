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

CONFIG_FILE = "/etc/factum/factum.yaml"

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

    def _load_locations(self, refresh=True):
        """
        Load all librenms locations into memory
        """
        if not refresh:
            if self.locations:
                return
        try:
            r = self.call_api(endpoint="/resources/locations")
            locations = AttrDict()
            data = json.loads(r.text, object_pairs_hook=AttrDict)
            for location in data["locations"]:
                locations[location.location] = location
            self.locations = locations
        except requests.exceptions.HTTPError as err:
            raise LibrenmsException("Cannot load librenms interfaces into memory: %s" % err)

    def clear_cache(self):
        """
        Remove entries in cache, forcing reload when needed
        """
        self.devices = AttrDict()
        self.interfaces = AttrDict()
        self.locations = AttrDict()

    def _format_name(self, name):
        if name.find('.') < 0:
            name = name + "." + self.config.default_domain
        return name

    def get_device(self, name=None, device_id=None):
        self._load_devices()
        if device_id:
            for name, device in self.devices.items():
                if device.device_id == device_id:
                    return device
            raise LibrenmsException(f"Unknown device with device_id {device_id}")
        
        try:
            name = self._format_name(name)
            return self.devices[name]
        except (KeyError, TypeError):
            raise LibrenmsException(f"Unknown device with name {name}")

    def get_devices(self, refresh=False):
        if refresh:
            self.clear_cache()
        self._load_devices()
        return self.devices
    
#    def create_device(self, name=None, force_add=0):
    def create_device(self, name=None, force_add=0, version=None, community=None):       
        name = self._format_name(name)
        data = AttrDict()
        data.hostname = name
        data.version = self.config.librenms.snmp.version
        data.force_add = force_add
        if version:
            data.version = version
        if community:
            data.community = community

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

    def set_device_parent(self, name=None, device_id=None, parents=None):
        """
        Set parents on a device
        parents is a list, each entry is one parent name

        Librenms does not have corresponding api, we get the current parents from the device,
        then remove/add parents until we have the desired list
        """
        # get current parents
        device_parents_id = AttrDict()
        device_parents_name = AttrDict()
        device = self.get_device(name=name, device_id=device_id)
        if device.dependency_parent_id:
            for parent_id, name in zip(device.dependency_parent_id.split(","), device.dependency_parent_hostname.split(",")):
                device_parents_id[parent_id] = name
                device_parents_name[parent_id] = parent_id

        wanted_parents_id = AttrDict()
        if parents:
            for parent_name in parents:
                parent_name = self._format_name(parent_name)
                try:
                    tmp_device = self.get_device(name=parent_name)
                    wanted_parents_id[tmp_device.device_id] = tmp_device.hostname
                except self.exception as err:
                    print("      Unknown wanted parent %s on device %s" % (parent_name, device.hostname))

        delete_ids = set(device_parents_id).difference(set(wanted_parents_id)) #  The returned set contains items that exist only in the first set, and not in both sets.
        create_ids = set(wanted_parents_id).difference(set(device_parents_id)) #  The returned set contains items that exist only in the first set, and not in both sets.

        if delete_ids:
            print("Device %s, delete parents_id %s" % (device.hostname, delete_ids))
            for device_id in delete_ids:
                try:
                    data = { "parent_ids": str(device_id) }
                    r = self.call_api(method="DELETE", endpoint=f"/devices/{device.device_id}/parents", data=data)
                    print("result", r)
                    # todo update cache
                except requests.exceptions.HTTPError as err:
                    raise LibrenmsException(f"Error setting parents on device_id {device_id}: {err}")
            return r

        if create_ids:
            print("Device %s, create parents_id %s" % (device.hostname, create_ids))
            for device_id in create_ids:
                try:
                    data = { "parent_ids": str(device_id) }
                    r = self.call_api(method="POST", endpoint=f"/devices/{device.device_id}/parents", data=data)
                    print("result", r)
                    # todo update cache
                except requests.exceptions.HTTPError as err:
                    raise LibrenmsException(f"Error setting parents on device_id {device.device_id}: {err}")

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
        Returns all locations as a dict. Key is location string
        """
        self._load_locations()
        return self.locations

    def get_location(self, location=None, location_id=None):
        """
        Get a location
        This API does not exist in Librenms, use the in-memory cache of all locations

        If location is not None use it, otherwise use location_id
        If location not found, return None
        """
        self._load_locations()
        if location:
            if location in self.locations:
                return self.locations[location]
            return None
        for location in self.locations:
            if location.id == location_id:
                return location
        return None

    def add_location(self, location: str=None, lat: float=None, lng: float=None):
        """
        Add a location
        Returns location_id if successfull else None
        """
        data = AttrDict(location=location)
        if lat:
            data.lat = lat
        else:
            data.lat = 0.001
        if lng:
            data.lng = lng
        else:
            data.lng = 0.001
        r = self.call_api(method="POST", endpoint=f"/locations", data=data)
        res = r.json()
        print("res", res)
        if res.get("status", "") != "ok":
            return None
        location_id = int(res["message"].split("#")[1])

        # Librenms add_location requires lat, lng
        # edit_location accepts None, so adjust
        r = self.edit_location(location=location_id, lat=lat, lng=lng)

        self._load_locations(refresh=True)
        return location_id

    def delete_location(self, location: str=None):
        """
        Delete a location
        Returns True if ok
        """
        r = self.call_api(method="DELETE", endpoint=f"/locations/{location}")
        res = r.json()
        if res.get("status", "") != "ok":
            return False
        self._load_locations(refresh=True)
        return True

    def edit_location(self, location: str=None, lat: float=None, lng: float=None):
        """
        Update a location data
        Returns True if ok
        """
        data = AttrDict()
        if lat:
            data.lat = lat
        if lng:
            data.lng = lng
        if not data:
            return True    # No change        

        r = self.call_api(method="PATCH", endpoint=f"/locations/{location}", data=data)
        res = r.json()
        if res.get("status", "") != "ok":
            return False
        self._load_locations(refresh=True)
        return True

    def set_device_location(self, name=None, location: str = None, lat: float = None, lng: float = None):
        """
        Set the location on a device
        Returns True if ok
        """
        loc = self.get_location(location)
        if loc:
            location_id = loc.id
            # location exist, check if data is modified
            data = AttrDict()
            if loc.lng != lng:
                data.lng = lng
            if loc.lat != lat:
                data.lat = lat
            if len(data):
                res = self.edit_location(location=location, lat=lat, lng=lng)
                if not res:
                    raise KeyError("Location could not be updated")
                loc = self.get_location(location)
                if loc is None:
                    raise KeyError("Location could not be retrieved after update")

        else:
            # location does not exist, create new location
            location_id = self.add_location(location=location, lat=lat, lng=lng)
            if not location_id:
                raise KeyError("Location could not be created")

        data = AttrDict(location_id=location_id)
        r = self.update_device(name=name, data=data)
        return r.get("status", "") == "ok"


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
        "get_location",
        "set_device_location",
    ])
    parser.add_argument("-n", "--name", default=None)
    parser.add_argument("--parent", default=[], action="append")
    parser.add_argument("--pretty", default=False, action="store_true")
    parser.add_argument("--location")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lng", type=float)
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

    elif cmd == "get_location":
        location = librenms_mgr.get_location(args.name)
        abutils.pprint(location)

    elif cmd == "set_device_location":
        if not args.name:
            abutils.die("Name is required")
        if not args.location:
            abutils.die("Location is required")

        r = librenms_mgr.set_device_location(
            name=args.name,
            location=args.location,
            lat=args.lat,
            lng=args.lng)

    else:
        abutils.die(f"Unknown command {cmd}")


if __name__ == '__main__':
    main()
