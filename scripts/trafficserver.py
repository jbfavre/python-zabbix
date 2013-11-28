#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Apache TrafficServer monitoring from Zabbix.
    - Uses python-zabbix module from https://github.com/jbfavre/python-zabbix
    - Performs an HTTP request on http://ats_server/_stats, parse json output,
        add items and send them to Zabbix server.
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.
'''
import sys
import optparse
import platform
import urllib2
import simplejson

import zabbix

__version__="0.0.2"

ITEM_BL = [
    'proxy.process.version.server.build_date',
    'proxy.process.version.server.build_machine',
    'proxy.process.version.server.build_number',
    'proxy.process.version.server.build_person',
    'proxy.process.version.server.build_time',
    'proxy.process.version.server.long',
    'proxy.process.version.server.short'
]

ATS_BOOLEAN_MAPPING = { "False": 0,
                        "True": 1 }
ATS_STATE_MAPPING = { "green": 0,
                      "yellow": 1,
                      "red": 2 }

ATS_CONN_ERR = "ERR - unable to get data from ATS [%s]"
ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
    ''' Parse the script arguments
    '''
    parser = optparse.OptionParser(description="Get TrafficServer statistics, "
                                    "format them and send the result to Zabbix")

    parser.add_option("-d", "--dry-run", action="store_true",
                               help="Performs TrafficServer API calls but do not "
                                    "send anything to the Zabbix server. Can be "
                                    "used for both Update & Discovery mode")
    parser.add_option("-D", "--debug", action="store_true",
                               help="Enable debug mode. This will prevent bulk "
                                    "send operations and force sending items one "
                                    "after the other, displaying result for each "
                                    "one")
    parser.add_option("-v", "--verbose", action="store_true",
                               help="When used with debug option, will force value "
                                    "display for each items managed. Beware that it "
                                    "can be pretty much verbose, specialy for LLD")

    general_options = optparse.OptionGroup(parser, "Apache TrafficServer cluster "
                                                   "configuration options")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="Apache TrafficServer hostname")
    general_options.add_option("-p", "--port", default=80,
                               help="Apache TrafficServer port"
                                    "Default is 80")

    parser.add_option_group(general_options)

    zabbix_options = optparse.OptionGroup(parser, "Zabbix configuration")
    zabbix_options.add_option("--zabbix-server", metavar="HOST", default="localhost",
                               help="The hostname of Zabbix server or "
                                    "proxy, default is localhost.")
    zabbix_options.add_option("--zabbix-port", metavar="PORT", default=10051,
                               help="The port on which the Zabbix server or "
                                    "proxy is running, default is 10051.")
    parser.add_option_group(zabbix_options)

    (options, args) = parser.parse_args()

    return (options, args)

def main():
    (options, args) = parse_args()
    data = {}
    rawjson = ""
    zbxret = 0

    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    zbx_container = zabbix.DataContainer("items", options.zabbix_server, int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)

    try:
        request = urllib2.Request( ("http://%s:%d/_stats" % (options.host, int(options.port))) )
        opener  = urllib2.build_opener()
        rawjson = opener.open(request)
    except urllib2.URLError as e:
        if options.debug:
            print ATS_CONN_ERR % e.reason
        return 1
    else:

        if (rawjson):
            json = simplejson.load(rawjson)
            for item in json['global']:
                if item not in ITEM_BL:
                    zbx_container.add_item( hostname, ("ats.%s" % item), json['global'][item])

        zbx_container.add_item(hostname, "ats.zbx_version", __version__)

        try:
            zbxret = zbx_container.send(zbx_container)
        except zabbix.SenderException as zbx_e:
            if options.debug:
                print ZBX_CONN_ERR % zbx_e.err_text
            return 2
        else:
            return 0

if __name__ == "__main__":
    ret = main()
    print ret
