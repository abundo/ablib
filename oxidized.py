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
        self.elements = None
        if load:
            self.load_elements()

    def __len__(self):
        return len(self.elements)

    def load_elements(self):
        self.elements = AttrDict()
        with open(self.config.router_db.dst, 'r') as f:
            for line in f.readlines():
                tmp = line.strip().split(":")
                if len(tmp) < 2:
                    print("Ignoring line ", line)
                    continue
                element = AttrDict()
                element.hostname = tmp[0]
                element.model = tmp[1]
                self.elements[element.hostname] = element

    def get_elements(self):
        return self.elements
    
    def get_element_interfaces(self, hostname):
        return None
    
    def get_element_config(self, name):
        """
        Fetch last element configuration, for an element
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
    
    def save_elements(self, filename, elements, ignore_models = None):
        if ignore_models is None:
            ignore_models = {}
        count = 0
        with open(filename, 'w') as f:
            for hostname, element in elements.items():
                # Element API is 'platform' oxidized calls it 'model'
                if 'platform' in element:
                    model = element['platform']
                    if model and model not in ignore_models:
                        if hostname == element['ipv4_addr']:
                            f.write("%s:%s\n" % (element['ipv4_addr'], model))
                        else:
                            f.write("%s:%s\n" % (element['hostname'], model))
                        count += 1
                else:
                    print("backup_oxidized is False for %s" % hostname)
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
                        choices=["get_elements", 
                                 "get_element_config",
                                 "reload",
                                 ])
    parser.add_argument("--router_db", default="/etc/oxidized/router.db")
    parser.add_argument("-H", "--hostname", default=None)
    args = parser.parse_args()

    oxidized_mgr = Oxidized_Mgr(config=config.oxidized)

    if args.cmd == 'get_elements':
        element_list = oxidized_mgr.get_elements()
        for hostname, element in element_list.items():
            print(hostname, element)
        print("Elements: %5d elements" % len(element_list))

    elif args.cmd == "get_element_config":
        if args.hostname is None:
            utils.die("Must specify hostname")
        conf = oxidized_mgr.get_element_config(args.hostname)
        print(conf)

    elif args.cmd == 'reload':
        oxidized_mgr.reload()

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
