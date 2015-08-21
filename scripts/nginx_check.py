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

class NginxServer(object):

    __version__="0.0.8"
    ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

    NGINX_CONN_ERR = "ERR - unable to get data from NGINX [%s]"

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser(description="Get Nginx statistics, "
                                        "format them and send the result to Zabbix")

        parser.add_option("-d", "--dry", action="store_true",
                                   help="Performs Nginx calls but do not "
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

        general_options = optparse.OptionGroup(parser, "Nginx "
                                                       "configuration options")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="Server FQDN")
        general_options.add_option("-E", "--endpoint", metavar="ENDPOINT", default="localhost",
                                   help="Nginx endpoint")
        general_options.add_option("-p", "--port", default=80,
                                   help="Nginx port"
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

        return parser.parse_args()

    def _init_container(self):
        zbx_container = protobix.DataContainer(
            data_type = 'items',
            zbx_host  = self.options.zabbix_server,
            zbx_port  = int(self.options.zabbix_port),
            debug     = self.options.debug,
            dryrun    = self.options.dry
        )
        return zbx_container

    def run(self):
        (self.options, args) = self._parse_args()
        if self.options.host == 'localhost':
            hostname = socket.getfqdn()
        else:
            hostname = self.options.host

        # Step 1: init container
        try:
            zbx_container = self._init_container()
            zbx_container.data_type = 'items'
        except:
            return 1

        # Step 2: get data
        try:
            request = urllib2.Request( ("http://%s:%d/nginx_status" % (self.options.endpoint, int(self.options.port))))
            opener  = urllib2.build_opener()
            rawdata = opener.open(request, None, 1)
        except urllib2.URLError as e:
            if self.options.debug:
                print self.NGINX_CONN_ERR % e.reason
            return 2

        # Step 3: format & load data into container
        try:
            if (rawdata):
                lines = rawdata.read(1000).splitlines(False)
                items = {}
                items['active_connections'] = lines[0].replace("Active connections: ", "")
                items['accepted_connections'] = lines[2].split(" ")[1]
                items['handled_connections'] = lines[2].split(" ")[2]
                items['handled_requests'] = lines[2].split(" ")[3]
                items['reading'] = re.findall(r'Reading: (\d+)', lines[3])[0]
                items['writing'] = re.findall(r'Writing: (\d+)', lines[3])[0]
                items['waiting'] = re.findall(r'Waiting: (\d+)', lines[3])[0]
                for item in items:
                    zbx_container.add_item( hostname, ("nginx.%s" % item), items[item])
            zbx_container.add_item(hostname, "nginx.zbx_version", self.__version__)
        except:
            return 3

        # Step 4: send container data to Zabbix server
        try:
            zbx_container.send(zbx_container)
        except protobix.SenderException as zbx_e:
            if self.options.debug:
                print self.ZBX_CONN_ERR % zbx_e.err_text
            return 4
        # Everything went fine. Let's return 0 and exit
        return 0

if __name__ == '__main__':
    ret = NginxServer().run()
    print ret
    sys.exit(ret)