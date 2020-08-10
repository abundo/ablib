#!/usr/bin/env python3
"""
Classes to handle Icinga2
"""

import os
import sys
import requests
import datetime
import json
from operator import attrgetter

from orderedattrdict import AttrDict
import ablib.utils as utils

# ----- Start of configuration items -----

CONFIG_FILE="/etc/abtools/abtools_icinga.yaml"

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
            "Accept": "application/json" ,
            'X-HTTP-Method-Override': 'GET',
            }
        postdata = {
#            "attrs": [ "name", "state", "acknowledgement"] #, "last_check_result"],
            "filter": "host.state!=0 && host.acknowledgement==0",
        }
        url = self.config.api.url + "/v1/objects/hosts"  #?attrs=name&attrs=state", #&attrs=last_check_result", 
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
        # utils.pretty_print("data", data)
        for host in data["results"]:
            attrs = host["attrs"]

            state = Host_State()
            state.name = host["name"]
            state.state = self.get(host, "attrs.state")
            state.address = self.get(host, "attrs.address")
            state.address6 = self.get(host, "attrs.address6")
            state.last_hard_state = self.get(host, "attrs.last_hard_state")
            state.last_hard_state_changed = self.get(host, "attrs.last_hard_state_change")
            state.last_hard_state_changed = utils.dt_from_timestamp(state.last_hard_state_changed)
            state.notes = self.get(host, "attrs.notes")
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
            "Accept": "application/json" ,
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
        # utils.pretty_print("data", data)
        for service in data["results"]:
            # utils.pretty_print("service", service)
            attrs = service["attrs"]
            state = Service_State()

            # Host
            state.host_name = self.get(attrs, "host_name")

            # Service
            state.name = attrs["name"]
            state.state = self.get(attrs, "state")
            state.last_hard_state = self.get(attrs, "last_hard_state")
            state.last_hard_state_changed = self.get(attrs, "last_hard_state_change")
            state.last_hard_state_changed = utils.dt_from_timestamp(state.last_hard_state_changed)
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
        result = []

        headers = { 
            "Accept": "application/json" ,
            }
        postdata = {
            # "attrs": [ "name", "state", "acknowledgement"]
            #"filter": "service.state!=0 && service.acknowledgement==0"
        }
        url = self.config.api.url + "/v1/events?queue=abtools_icinga&types=CheckResult"
        r = requests.post(
            url,
            headers=headers, 
            auth=(self.config.api.username, self.config.api.password),
            data=json.dumps(postdata),
            verify=False, 
            stream=True
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
        config = utils.yaml_load(CONFIG_FILE)
    except utils.UtilException as err:
        utils.die("Cannot load configuration file, err: %s" % err)

    icinga = Icinga(config=config.icinga)

    if 0:
        print("Hosts down, not acknowledged")
        state_down = icinga.get_hosts_down()
        for state in state_down:
            utils.pretty_print("", state)
            print()
    if 0:
        print("Services down, not acknowledged")
        state_down = icinga.get_services_down()
        for state in state_down:
            utils.pretty_print("", state)
            print()
    
    if 1:
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
                    print(json.loads(line))
            else:
                break
        


if __name__ == "__main__":
    main()


"""
Example output

HOST

{   'attrs': {   '__name': 'asw1040.net.piteenergi.se',
                 'acknowledgement': 0.0,
                 'acknowledgement_expiry': 0.0,
                 'action_url': '',
                 'active': True,
                 'address': '10.20.9.40',
                 'address6': '',
                 'check_attempt': 1.0,
                 'check_command': 'hostalive',
                 'check_interval': 60.0,
                 'check_period': '',
                 'check_timeout': None,
                 'command_endpoint': '',
                 'display_name': 'asw1040.net.piteenergi.se',
                 'downtime_depth': 0.0,
                 'enable_active_checks': True,
                 'enable_event_handler': True,
                 'enable_flapping': False,
                 'enable_notifications': True,
                 'enable_passive_checks': True,
                 'enable_perfdata': True,
                 'event_command': '',
                 'flapping': False,
                 'flapping_current': 0.0,
                 'flapping_last_change': 0.0,
                 'flapping_threshold': 0.0,
                 'flapping_threshold_high': 30.0,
                 'flapping_threshold_low': 25.0,
                 'force_next_check': False,
                 'force_next_notification': False,
                 'groups': [],
                 'ha_mode': 0.0,
                 'icon_image': '',
                 'icon_image_alt': '',
                 'last_check': 1567509489.841116,
                 'last_check_result': {   'active': True,
                                          'check_source': 'peicinga.net.piteenergi.se',
                                          'command': [   '/usr/lib/nagios/plugins/check_ping',
                                                         '-H',
                                                         '10.20.9.40',
                                                         '-c',
                                                         '5000,100%',
                                                         '-w',
                                                         '3000,80%'],
                                          'execution_end': 1567509489.841052,
                                          'execution_start': 1567509459.837625,
                                          'exit_status': 2.0,
                                          'output': 'PING CRITICAL - Packet '
                                                    'loss = 100%',
                                          'performance_data': [   'rta=5000.000000ms;3000.000000;5000.000000;0.000000',
                                                                  'pl=100%;80;100;0'],
                                          'schedule_end': 1567509489.841116,
                                          'schedule_start': 1567509459.837365,
                                          'state': 2.0,
                                          'ttl': 0.0,
                                          'type': 'CheckResult',
                                          'vars_after': {   'attempt': 1.0,
                                                            'reachable': True,
                                                            'state': 2.0,
                                                            'state_type': 1.0},
                                          'vars_before': {   'attempt': 1.0,
                                                             'reachable': True,
                                                             'state': 2.0,
                                                             'state_type': 1.0}},
                 'last_hard_state': 1.0,
                 'last_hard_state_change': 1561193227.707049,
                 'last_reachable': True,
                 'last_state': 1.0,
                 'last_state_change': 1561192933.938269,
                 'last_state_down': 1567509489.841129,
                 'last_state_type': 1.0,
                 'last_state_unreachable': 0.0,
                 'last_state_up': 1561192845.184672,
                 'max_check_attempts': 6.0,
                 'name': 'asw1040.net.piteenergi.se',
                 'next_check': 1567509547.951139,
                 'notes': '',
                 'notes_url': '',
                 'original_attributes': None,
                 'package': '_etc',
                 'paused': False,
                 'retry_interval': 30.0,
                 'severity': 136.0,
                 'source_location': {   'first_column': 1.0,
                                        'first_line': 746.0,
                                        'last_column': 39.0,
                                        'last_line': 746.0,
                                        'path': '/etc/icinga2/conf.d/gen-hosts.conf'},
                 'state': 1.0,
                 'state_type': 1.0,
                 'templates': ['asw1040.net.piteenergi.se', 'generic-host'],
                 'type': 'Host',
                 'vars': {   'notification': {   'mail': {   'groups': [   'icingaadmins']}},
                             'pe_comments': 'Traversvägen 7',
                             'pe_manufacturer': 'Cisco',
                             'pe_model': 'SG300-10',
                             'pe_platform': 'ciscosmb',
                             'pe_role': 'Access-switch kundplacerad',
                             'pe_site_name': ''},
                 'version': 0.0,
                 'volatile': False,
                 'zone': ''},
    'joins': {},
    'meta': {},
    'name': 'asw1040.net.piteenergi.se',
    'type': 'Host'}


SERVICE

{   'attrs': {   '__name': 'becs.net.piteenergi.se!DHCP Scope Ownit_Inet - '
                           'summary',
                 'acknowledgement': 0.0,
                 'acknowledgement_expiry': 0.0,
                 'action_url': '',
                 'active': True,
                 'check_attempt': 1.0,
                 'check_command': 'passive',
                 'check_interval': 3600.0,
                 'check_period': '',
                 'check_timeout': None,
                 'command_endpoint': '',
                 'display_name': 'DHCP Scope Ownit_Inet - summary',
                 'downtime_depth': 0.0,
                 'enable_active_checks': False,
                 'enable_event_handler': True,
                 'enable_flapping': False,
                 'enable_notifications': True,
                 'enable_passive_checks': True,
                 'enable_perfdata': True,
                 'event_command': '',
                 'flapping': False,
                 'flapping_current': 11.200000000000001,
                 'flapping_last_change': 0.0,
                 'flapping_threshold': 0.0,
                 'flapping_threshold_high': 30.0,
                 'flapping_threshold_low': 25.0,
                 'force_next_check': False,
                 'force_next_notification': False,
                 'groups': [],
                 'ha_mode': 0.0,
                 'host_name': 'becs.net.piteenergi.se',
                 'icon_image': '',
                 'icon_image_alt': '',
                 'last_check': 1567509063.0,
                 'last_check_result': {   'active': False,
                                          'check_source': 'peicinga.net.piteenergi.se',
                                          'command': None,
                                          'execution_end': 1567509063.0,
                                          'execution_start': 1567509063.0,
                                          'exit_status': 0.0,
                                          'output': '15 free addresses, 171 '
                                                    'assigned addresses',
                                          'performance_data': [],
                                          'schedule_end': 1567509063.0,
                                          'schedule_start': 1567509063.0,
                                          'state': 1.0,
                                          'ttl': 0.0,
                                          'type': 'CheckResult',
                                          'vars_after': {   'attempt': 1.0,
                                                            'reachable': True,
                                                            'state': 1.0,
                                                            'state_type': 1.0},
                                          'vars_before': {   'attempt': 1.0,
                                                             'reachable': True,
                                                             'state': 1.0,
                                                             'state_type': 1.0}},
                 'last_hard_state': 1.0,
                 'last_hard_state_change': 1567505462.865385,
                 'last_reachable': True,
                 'last_state': 1.0,
                 'last_state_change': 1567505462.865385,
                 'last_state_critical': 1567501862.241972,
                 'last_state_ok': 1557994262.542834,
                 'last_state_type': 1.0,
                 'last_state_unknown': 0.0,
                 'last_state_unreachable': 0.0,
                 'last_state_warning': 1567509063.069148,
                 'max_check_attempts': 6.0,
                 'name': 'DHCP Scope Ownit_Inet - summary',
                 'next_check': 1567512663.069156,
                 'notes': '',
                 'notes_url': '',
                 'original_attributes': None,
                 'package': '_etc',
                 'paused': False,
                 'retry_interval': 30.0,
                 'severity': 40.0,
                 'source_location': {   'first_column': 1.0,
                                        'first_line': 109.0,
                                        'last_column': 47.0,
                                        'last_line': 109.0,
                                        'path': '/etc/icinga2/conf.d/becs_dhcp_scopes.conf'},
                 'state': 1.0,
                 'state_type': 1.0,
                 'templates': [   'DHCP Scope Ownit_Inet - summary',
                                  'dhcp-scope-free-addresses',
                                  'generic-service'],
                 'type': 'Service',
                 'vars': None,
                 'version': 0.0,
                 'volatile': False,
                 'zone': ''},
    'joins': {},
    'meta': {},
    'name': 'becs.net.piteenergi.se!DHCP Scope Ownit_Inet - summary',
    'type': 'Service'}


"""
