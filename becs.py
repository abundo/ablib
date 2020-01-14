#!/usr/bin/env python3 
"""
Class to handle BECS, using BECS ExtAPI

dependencies:
    sudo pip3 install zeep orderedattrdict
"""

import sys
import time
import argparse
import sqlite3

import zeep
from orderedattrdict import AttrDict

sys.path.insert(0, "/opt")
import ablib.utils as utils

# ----- Start of configuration items ----------------------------------------

CONFIG_FILE="/etc/abtools/abtools_control.yaml"

# ----- End of configuration items ------------------------------------------

# Load configuration
config = utils.load_config(CONFIG_FILE)


class BECS:

    def __init__(self, eapi_url=None, username=None, password=None):
        self.eapi_url = eapi_url
        self.username = username
        self.password = password

        self.client = zeep.Client(wsdl=self.eapi_url, 
                                  settings=zeep.Settings(strict=False)
                                  )
        self.elements_oid = {}         # key is oid, value is object
        self.obj_cache = {}            # key is oid, value is object
        self.login()

    def login(self):
        self.session = self.client.service.sessionLogin({
            "username": self.username, 
            "password": self.password
            })
        self._soapheaders = {
            "request": {"sessionid": self.session["sessionid"]},
        }

    def logout(self):
        self.client.service.sessionLogout({}, _soapheaders=self._soapheaders)

    def get_object(self, oid):
        """
        Fetch one object, using a cache
        retuns object, or None if not found
        """
        if oid in self.obj_cache:
            return self.obj_cache[oid]

        data = self.client.service.objectFind(
            {
                "queries": [ 
                    { "queries": { "oid" : oid } }
                ] 
            },
            _soapheaders=self._soapheaders
        )
        if data["objects"]:
            obj = data["objects"][0]
            self.obj_cache[oid] = obj
            return obj
        return None

    def search_opaque(self, oid, name):
        """
        Search for first occurence of an opaque name, walking upwards in tree
        Note, does not handle arrays
        If not found, return None
        """
        value = None
        while True:
            obj = self.get_object(oid)
            if obj is None:
                return value

            if "opaque" in obj:
                for opaque in obj["opaque"]:
                    if opaque["name"] == name:
                        if len(opaque["values"]):
                            value = opaque["values"][0]["value"]
                            return value

            if obj["parentoid"]:
                oid = obj["parentoid"]
                if oid != 1:
                    continue
            return None

    def search_parent(self, oid):
        """
        Search for parents, going upwards towards the root
        Returns first found parent name or None if none found
        Parents can either be an element-attach, or an opaque named "parents"
        """
        parents = None
        check_element = False   # No match on first element (ourself)
        while True:
            obj = self.get_object(oid)
            if obj is None:
                return parents

            if "opaque" in obj:
                for opaque in obj["opaque"]:
                    if opaque["name"] == "parents":
                        if len(opaque["values"]):
                            parents = opaque["values"][0]["value"]
                            return parents

            if check_element and obj["class"] == "element-attach":
                parents = obj["name"]
                return parents
            check = True

            if obj["parentoid"]:
                oid = obj["parentoid"]
                if oid != 1:
                    continue
            return None

    def get_elements(self, start_oid=1):
        """
        Get all elements (element-attach) from BECS
        """
        self.elements_oid = {}        # key is oid, value is element

        data = self.client.service.objectTreeFind(
            {
                "oid": start_oid,
                "classmask": "element-attach",
                "walkdown": 0,
            } , 
            _soapheaders=self._soapheaders
        )

        # Build up dictionary, to easy get get/handle parent/child relations
        # make sure name is FQDN
        print("----- build dict with elements -----")
        for element in data["objects"]:
            element["name"] = element["name"].lower()
            if "." not in element["name"]:
                element["name"] += "." + config.default_domain
            self.elements_oid[element["oid"]] = element

        # For each element
        #   find the parent element
        #   find alarm_destination
        #   find alarm_timeperiod
        print("----- build parents, alarm_destination etc -----")
        for oid, element in self.elements_oid.items():
            parents = self.search_parent(oid)
            if parents:
                _parents = []
                for parent in parents.split(","):
                    if "." not in parent:
                        parent += "." + config.default_domain
                    _parents.append(parent)
                element["_parents"]  = ",".join(_parents)
            else:
                element["_parents"] = ""
            
            element["_alarm_destination"] = self.search_opaque(oid, "alarm_destination")
            element["_alarm_timeperiod"] = self.search_opaque(oid, "alarm_timeperiod")


    def get_interface(self, oid):
        """
        Get interfaces and their IP addresses for an element-attach
        Returns a list of interface, each interface is an AttrDict
        """
        data = self.client.service.objectTreeFind(
            {
                "oid": oid,
                "classmask": "interface,resource-inet",
                "walkdown": 2,
            } , 
            _soapheaders = self._soapheaders
        )
        #print(interface_data)

        res = []

        # Get IP address for each interface
        for interface in data["objects"]:
            if interface["class"] == "interface":
                flags = interface["flags"]
                if flags is None:
                    enabled = True
                else:
                    enabled = flags.find("disable") < 0
                # search for the resource-inet in response
                prefix = None
                for resource_inet in data["objects"]:
                    if resource_inet["class"] == "resource-inet" and resource_inet["parentoid"] == interface["oid"]:
                        prefix = "%s/%d" % (resource_inet["resource"]["address"], resource_inet["resource"]["prefixlen"])
                        break

                d = AttrDict()
                d.name = interface["name"]
                d.role = interface["role"]
                d.prefix = prefix
                d.enabled = enabled
                res.append(d)
        return res
