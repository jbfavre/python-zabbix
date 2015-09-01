#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Apache TrafficServer monitoring from Zabbix.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
    - Performs an HTTP request on http://ats_server/_stats, parse json output,
        add items and send them to Zabbix server.
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.
'''
import sys,os
import optparse
import socket
import urllib2
import simplejson
import protobix

class TrafficServer(protobix.SampleProbe):

    __version__ = '0.0.8'

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

    def _get_stats(self):
        rawdata = urllib2.build_opener().open(
            "http://%s:%s/_stats" % (self.options.host, self.options.port),
            None, # data
            1 # timeout
        )
        json = None
        if (rawdata):
            json = simplejson.load(rawdata)
        return json

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( TrafficServer, self)._parse_args()

        # TrafficServer options
        ats_options = optparse.OptionGroup(
            parser,
            "Apache TrafficServer cluster configuration options"
        )
        ats_options.add_option(
            "-H", "--host", default="localhost",
            help="Apache TrafficServer hostname"
        )
        ats_options.add_option(
            "-P", "--port", default=80,
            help="Apache TrafficServer port. Default is 80"
        )
        parser.add_option_group(ats_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host

    def _get_metrics(self):
        data = {}
        json = self._get_stats()
        for item in json['global']:
            if item not in self.ITEM_BL:
                data["ats.%s" % item] = json['global'][item]
        data['ats.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = TrafficServer().run()
    print ret
    sys.exit(ret)