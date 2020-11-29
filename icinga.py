#!/usr/bin/env python3
"""
Classes to handle Icinga2
"""

# python standard modules
import os
import json
from operator import attrgetter

# modules installed with pip
import requests
from orderedattrdict import AttrDict

# my modules
import ablib.utils as abutils


# ----- Start of configuration items -----

CONFIG_FILE = "/etc/abcontrol/abcontrol.yaml"

# ----- End of configuration items -----


class IcingaException(Exception):
    pass


class Host_State(AttrDict):
    def __init__(self):
        super().__init__()
        self.acknowledgement = 0
        self.state = 0
        self.address = ""
        self.address6 = ""
        self.last_hard_state = ""
        self.last_hard_state_changed = ""

        self.notes = ""

        self.pe_comments = ""
        self.pe_location = ""
        self.pe_manufacturer = ""
        self.pe_model = ""
        self.pe_platform = ""
        self.pe_role = ""
        self.pe_site_name = ""


class Service_State(AttrDict):
    def __init__(self):
        super().__init__()
        self.acknowledgement = 0
        self.state = 0
        self.last_hard_state = ""
        self.last_hard_state_changed = ""

        self.notes = ""


class Icinga:
    """
    Manage icinga2
    """
    Exception = IcingaException

    def __init__(self, config=None):
        self.config = config
    
    def get(self, attr, keys, default=""):
        """
        Helper function to get attributes
        """
        try:
            for key in keys.split("."):
                attr = attr[key]
            return attr
        except KeyError:
            print("didnt find %s" % keys)
            return default

    def state_to_str(self, state):
        if state == 0:
            return "WARNING"
        if state == 1:
            return "WARNING"
        if state == 2:
            return "CRITICAL"
        return "UNKNOWN"

    def reload(self):
        """
        Reload icinga, use when configuration has changed
        """
        os.system("systemctl reload icinga2.service")

    def quote(self, s):
        """
        Quote special characters, so Icinga does not barf on the config
        https://icinga.com/docs/icinga2/latest/doc/17-language-reference/#string-literals-escape-sequences
        """
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\"')
        s = s.replace('\t', '\\t')
        s = s.replace('\r', '\\r')
        s = s.replace('\n', '\\n')
        return '"%s"' % s

    def get_hosts_down(self):
        """
        Get all hosts, which is down but not acknowledged
        """
        result = []
        headers = {
            "Accept": "application/json",
            'X-HTTP-Method-Override': 'GET',
        }
        postdata = {
            # "attrs": [ "name", "state", "acknowledgement"] #, "last_check_result"],
            "filter": "host.state!=0 && host.acknowledgement==0",
        }
        url = self.config.api.url + "/v1/objects/hosts"  # ?attrs=name&attrs=state", #&attrs=last_check_result",
        r = requests.get(
            url,
            headers=headers,
            auth=(self.config.api.username, self.config.api.password),
            data=json.dumps(postdata),
            verify=False,
        )
        if r.status_code != 200:
            raise IcingaException("Cannot fetch data from Icinga API, status_code %s" % r.status_code)
        
        data = r.json()
        # abutils.pprint(data, "data")
        for host in data["results"]:
            state = Host_State()
            state.name = host["name"]
            state.state = self.get(host, "attrs.state")
            state.address = self.get(host, "attrs.address")
            state.address6 = self.get(host, "attrs.address6")
            state.last_hard_state = self.get(host, "attrs.last_hard_state")
            state.last_hard_state_changed = self.get(host, "attrs.last_hard_state_change")
            state.last_hard_state_changed = abutils.dt_from_timestamp(state.last_hard_state_changed)
            state.notes = self.get(host, "attrs.notes")
            state.pe_location = self.get(host, "attrs.vars.pe_location")
            state.pe_comments = self.get(host, "attrs.vars.pe_comments")
            state.pe_manufacturer = self.get(host, "attrs.vars.pe_manufacturer")
            state.pe_model = self.get(host, "attrs.vars.pe_model")
            state.pe_platform = self.get(host, "attrs.vars.pe_platform")
            state.pe_role = self.get(host, "attrs.vars.pe_role")
            state.pe_site_name = self.get(host, "attrs.vars.pe_site_name")

            result.append(state)

        # Sort result on last_hard_state_changed
        result = sorted(result, key=attrgetter("last_hard_state_changed"), reverse=True)
        return result

    def get_services_down(self):
        """
        Get all services, which are not up and not acknowledged.
        returns list of services
        """
        result = []

        headers = {
            "Accept": "application/json",
            'X-HTTP-Method-Override': 'GET',
        }
        postdata = {
            # "attrs": [ "name", "state", "acknowledgement"]
            "filter": "service.state!=0 && service.acknowledgement==0"
        }
        url = self.config.api.url + "/v1/objects/services"
        r = requests.get(
            url,
            headers=headers,
            auth=(self.config.api.username, self.config.api.password),
            data=json.dumps(postdata),
            verify=False,
        )
        if r.status_code != 200:
            raise IcingaException("Cannot fetch data from Icinga API, status_code %s" % r.status_code)
        
        data = r.json()
        # abutils.pprint(data, "data")
        for service in data["results"]:
            # abutils.pprint(service, "service")
            attrs = service["attrs"]
            state = Service_State()

            # Host
            state.host_name = self.get(attrs, "host_name")

            # Service
            state.name = attrs["name"]
            state.state = self.get(attrs, "state")
            state.last_hard_state = self.get(attrs, "last_hard_state")
            state.last_hard_state_changed = self.get(attrs, "last_hard_state_change")
            state.last_hard_state_changed = abutils.dt_from_timestamp(state.last_hard_state_changed)
            state.output = self.get(attrs, "last_check_result.output")
            state.notes = self.get(attrs, "notes")

            result.append(state)

        # Sort result on last_hard_state_changed
        result = sorted(result, key=attrgetter("last_hard_state_changed"), reverse=True)
        return result

    def get_events(self):
        """
        Get all events
        returns iterator
        """
        headers = {
            "Accept": "application/json",
        }
        postdata = {
            # "attrs": [ "name", "state", "acknowledgement"]
            # "filter": "service.state!=0 && service.acknowledgement==0"
        }
        url = self.config.api.url + "/v1/events?queue=abtools_icinga&types=CheckResult"
        r = requests.post(
            url,
            headers=headers,
            auth=(self.config.api.username, self.config.api.password),
            data=json.dumps(postdata),
            verify=False,
            stream=True,
        )
        if r.status_code != 200:
            raise IcingaException("Cannot fetch data from Icinga API, status_code %s" % r.status_code)

        return r
 

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
        "get_hosts_down",
        "get_services_down",
        "show_events",
    ])
    parser.add_argument("--name", default=None)
    parser.add_argument("--parent", default=[], action="append")
    parser.add_argument("--pretty", default=False, action="store_true")
    args = parser.parse_args()
    cmd = args.cmd

    icinga = Icinga(config=config.icinga)

    if cmd == "get_hosts_down":
        print("Hosts down, not acknowledged")
        state_down = icinga.get_hosts_down()
        for state in state_down:
            abutils.pprint(state)
            print()

    elif args.cmd == "get_services_down":
        print("Services down, not acknowledged")
        state_down = icinga.get_services_down()
        for state in state_down:
            abutils.pprint(state)
            print()

    elif args.cmd == "show_events":
        import signal
        global running
        running = True

        def signal_handler(sig, frame):
            """Trap ctrl-c, do to proper termination"""
            global running
            running = False

        signal.signal(signal.SIGINT, signal_handler)
        print("Streaming events")
        r = icinga.get_events()
        for line in r.iter_lines(decode_unicode=True):
            if running:
                if line:
                    data = json.loads(line)
                    abutils.pprint(data)
            else:
                break
    
    else:
        print(f"Internal error, cmd {args.cmd}")


if __name__ == "__main__":
    main()
