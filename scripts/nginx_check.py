#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2015 Tony Fouchard.
    Sample script for Zabbix integration with Nginx.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.
'''
import sys
import optparse
import socket
import urllib2
import simplejson
import re

import protobix

class NginxServer(protobix.SampleProbe):

    __version__ = '0.0.9'

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( NginxServer, self)._parse_args()

        general_options = optparse.OptionGroup(parser, "Nginx "
                                                       "configuration options")
        general_options.add_option('-H', '--host', default='localhost',
                                   help='Server FQDN')
        general_options.add_option('-E', '--endpoint', default='localhost',
                                   help='Nginx endpoint')
        general_options.add_option('-P', '--port', default=80,
                                   help='Nginx port. Default is 80')
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host

    def _get_metrics(self):
        data = {}
        request = urllib2.Request( ("http://%s:%d/nginx_status" % (self.options.endpoint, int(self.options.port))))
        opener  = urllib2.build_opener()
        rawdata = opener.open(request, None, 1)
        if (rawdata):
            lines = rawdata.read(1000).splitlines(False)
            data = {}
            data['nginx.active_connections'] = lines[0].replace("Active connections: ", "")
            data['nginx.accepted_connections'] = lines[2].split(" ")[1]
            data['nginx.handled_connections'] = lines[2].split(" ")[2]
            data['nginx.handled_requests'] = lines[2].split(" ")[3]
            data['nginx.reading'] = re.findall(r'Reading: (\d+)', lines[3])[0]
            data['nginx.writing'] = re.findall(r'Writing: (\d+)', lines[3])[0]
            data['nginx.waiting'] = re.findall(r'Waiting: (\d+)', lines[3])[0]
        data['nginx.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = NginxServer().run()
    print ret
    sys.exit(ret)