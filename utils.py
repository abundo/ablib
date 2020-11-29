#!/usr/bin/env python3

"""
Common utilities
"""

# python standard modules
import os
import sys
import yaml
import json
import pprint
import shutil
import filecmp
import datetime

# modules installed with pip
from orderedattrdict import AttrDict

pp = pprint.PrettyPrinter(indent=4)


class UtilException(Exception):
    pass


def die(msg, exitcode=1):
    print(msg)
    sys.exit(exitcode)


def pretty_print(msg, d):
    if not isinstance(d, (dict, list)):
        try:
            d = vars(d)
        except TypeError:
            pass
    if msg:
        print(msg)
    pp.pprint(d)


def pprint(d, msg=None):
    pretty_print(msg, d)


def now():
    return datetime.datetime.now().replace(microsecond=0)


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def dt_from_timestamp(t):
    return datetime.datetime.fromtimestamp(t).replace(microsecond=0)


def json_serial(obj):
    """
    JSON serializer for objects not serializable by default json code
    """
    if isinstance(obj, datetime.datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    return obj.to_dict()


def json_dumps(data, fp=None, **kwargs):
    return json.dump(data, fp=fp, default=json_serial, **kwargs)


def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=AttrDict):
    """
    Load Yaml document, replace all hashes/mappings with AttrDict
    """
    class Ordered_Loader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    Ordered_Loader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, Ordered_Loader)


def yaml_load(filename):
    with open(filename, "r") as f:
        try:
            data = ordered_load(f, yaml.SafeLoader)
            return data
        except yaml.YAMLError as err:
            raise UtilException("Cannot load YAML file %s, err: %s" % (filename, err))


def load_config(filename):
    """
    Helper to load YAML configuration file
    """
    try:
        config = yaml_load(filename)
    except UtilException as err:
        die("Cannot load configuration file, err: %s" % err)
    return config


def install_conf_file(src, dst, changed=False):
    """
    Compare the src file with the dst file, if different replace dst file with src file,
    and return True
    """
    replace_file = True
    if os.path.exists(dst):
        if filecmp.cmp(src, dst):
            replace_file = False

    if replace_file:
        shutil.copy(src, dst)
        changed = True

    return changed


def send_traceback():
    """
    Create a traceback and send to developer
    """
    import traceback
    import platform

    if sys.stdout.isatty():
        # We have a tty, show traceback on stdout
        print(traceback.format_exc())
    else:
        print("Sending email to developer")
        from ablib.email1 import Email
        msg = "<pre>\n"
        msg += "arguments:\n"
        for ix in range(len(sys.argv)):
            msg += "  %2d %s\n" % (ix, sys.argv[ix])
        msg += "\n"

        msg += traceback.format_exc()
        msg += "</pre>"
        print(msg)
        email = Email()
        email.send(
            recipient="anders@abundo.se",
            sender="noreply@piteenergi.se",
            subject="%s %s program error" % (platform.node(), sys.argv[0]),
            msg=msg
        )


def write_etc_hosts_file(devices):
    """
    Update /etc/hosts file with all devices primary_ipv4, from device-api
    Note: If you change the delemiter, you need to manually cleanup the hosts file
    """
    delemiter = "# ----- do not edit below - updated by a script -----"
    with open("/etc/hosts", "r+") as f:
        line = f.readline()
        while line:
            line = line.strip()
            if line == delemiter:
                print("  Delemiter found, writing %d entries." % len(devices))
                f.seek(f.tell())
                for hostname, device in devices.items():
                    primary_ip4 = device.get("primary_ip4", None)
                    # primary_ip6 = device.get("primary_ip6", None)
                    if primary_ip4:
                        addr4 = primary_ip4.address.split("/")[0]
                        if addr4 != hostname:
                            # short_hostname = hostname
                            tmp = "%-18s %s" % (addr4, hostname)
                            p = hostname.find(".")
                            if p >= 0:
                                tmp += "  %s" % hostname[:p]
                            f.write("%s\n" % tmp)
                f.write("# ----- end -----\n")
                f.truncate()
                return
            line = f.readline()


class BaseCLI:

    def __init__(self):
        import argparse
        self.parser = argparse.ArgumentParser()
        self.add_arguments2()
        self.add_arguments()
        self.args = self.parser.parse_args()

    def add_arguments2(self):
        """Superclass overrides this to add additional arguments"""

    def add_arguments(self):
        """Superclass overrides this to add additional arguments"""

    def run(self):
        raise ValueError("You must override the run() method")


class MyCLI:
    """
    Helper class, to construct a CLI
    """
    def __init__(self, name, **kwargs):
        # get all CLI modules
        self.cmds = AttrDict()
        current_module = sys.modules[name]
        for key in dir(current_module):
            if key.startswith("CLI_"):
                cls = getattr(current_module, key)
                self.cmds[key[4:]] = cls

        # get first arg, use as command
        if len(sys.argv) < 2:
            self.usage("No command specified, choose one of:")

        cmd = sys.argv.pop(1)
        if cmd not in self.cmds:
            self.usage("Unknown command '%s'" % cmd)

        obj = self.cmds[cmd](**kwargs)
        obj.run()

    def usage(self, msg):
        if msg:
            print(msg)
        for cmd in self.cmds:
            print("   ", cmd)
        sys.exit(1)
