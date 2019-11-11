#!/usr/bin/env python3
"""
Class to handle elements, using Element API
"""

import sys
import requests


class Elements_Mgr:
    def __init__(self, config=None):
        self.config = config
        self.elements = {}
        self._loaded = False

    def __len__(self):
        return len(self.elements)

    def load_elements(self):
        self.elements = {}
        r = requests.get(url=self.config["api"]["url"])
        self.elements = r.json()

    def get_element(self, hostname):
        if hostname in self.elements:
            return self.elements[hostname]
        r = requests.get(url=self.config["api"]["url"] + "/" + hostname)
        element = r.json()
        name = list(element.keys())[0]
        self.elements[name] = element
        return element

    def get_elements(self):
        if not self._loaded:
            self._loaded = True
            self.load_elements()
        return self.elements
    
    def get_element_interfaces(self, hostname):
        if hostname in self.elements:
            return self.elements[hostname]['interfaces']
        return None
    

def main():
    """
    Function tests
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cmd', required=True, 
                        choices=['get_elements', 
                                 ])
    parser.add_argument('--hostname', default=None)
    parser.add_argument("--api_url", required=True, default=None)
    args = parser.parse_args()

    # Create a dummy config
    config = {}
    config["api"] = {}
    config["api"]["url"] = args.api_url

    elements_mgr = Elements_Mgr(config=config)

    if args.cmd == 'get_elements':
        elements = elements_mgr.get_elements()
        for hostname, element in elements.items():
            print(hostname, element)
        print("Elements: %5d elements" % len(elements))
    else:
        print("Unknown command %s" % args.cmd)
 

if __name__ == '__main__':
    main()
