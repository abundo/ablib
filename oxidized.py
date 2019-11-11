#!/usr/bin/env python3
"""
Class to handle Oxidized
"""

import sys
import subprocess
from orderedattrdict import AttrDict


class Oxidized_Mgr:
    def __init__(self, config=None, load=True):
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
        """
        cmd = "curl -s %s/reload?format=json >/dev/null 2>&1" % self.config.url
        subprocess.run(cmd.split(" "))


def main():
    """
    Function tests
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, 
                        choices=["get_elements", 
                                 "reload",
                                 ])
    parser.add_argument("--url", default=None)
    parser.add_argument("--router_db", default="/etc/oxidized/router.db")
    args = parser.parse_args()

    # Create a dummy config instance
    config = AttrDict()
    config.url = args.url
    config.router_db = args.router_db

    oxidized_mgr = Oxidized_Mgr(config=config)

    if args.cmd == 'get_elements':
        element_list = oxidized_mgr.get_elements()
        for hostname, element in element_list.items():
            print(hostname, element)
        print("Elements: %5d elements" % len(element_list))

    elif args.cmd == 'reload':
        if args.url is None:
            print("Error: must specify URL")
        oxidized_mgr.reload()

    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
