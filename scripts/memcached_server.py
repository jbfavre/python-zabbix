#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with memcached.
'''
import optparse
import socket
import sys
import protobix
import memcache

class MemcachedServer(object):

    __version__="0.0.8"
    ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs Memcache call but do not send "
                                   "anything to the Zabbix server. Can be used "
                                   "for both Update & Discovery mode")
        parser.add_option("-D", "--debug", action="store_true",
                          help="Enable debug mode. This will prevent bulk send "
                               "operations and force sending items one after the "
                               "other, displaying result for each one")
        parser.add_option("-v", "--verbose", action="store_true",
                          help="When used with debug option, will force value "
                               "display for each items managed. Beware that it "
                               "can be pretty too much verbose, specialy for LLD")

        mode_group = optparse.OptionGroup(parser, "Program Mode")
        mode_group.add_option("--update-items", action="store_const",
                              dest="mode", const="update_items",
                              help="Get & send items to Zabbix. This is the default "
                                   "behaviour even if option is not specified")
        mode_group.add_option("--discovery", action="store_const",
                              dest="mode", const="discovery",
                              help="If specified, will perform Zabbix Low Level "
                                   "Discovery on Memcache. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

        general_options = optparse.OptionGroup(parser, "Memcache Configuration")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="Memcache server hostname")
        general_options.add_option("-p", "--port", help="Memcache server port",
                                   default=11211)
        parser.add_option_group(general_options)

        polling_options = optparse.OptionGroup(parser, "Zabbix configuration")
        polling_options.add_option("--zabbix-server", metavar="HOST",
                                   default="localhost",
                                   help="The hostname of Zabbix server or "
                                        "proxy, default is localhost.")
        polling_options.add_option("--zabbix-port", metavar="PORT", default=10051,
                                   help="The port on which the Zabbix server or "
                                        "proxy is running, default is 10051.")
        parser.add_option_group(polling_options)

        return parser.parse_args()

    def _get_metrics(self, memcache, hostname):
        data = {}
        data[hostname] = {}
        ''' FIXME
            add support for:
                * stats slabs
                * stats items
                * stats sizes <= /!\ look memcached /!\
        '''
        result = memcache.get_stats()
        for node_stats in result:
            server, stats = node_stats
            host = server.split(':')[0]
            if not host in data:
                data[host] = {}
            for stat in stats:
                data[host]["memcached.%s"%stat] = stats[stat]
        return data

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
            mc = memcache.Client(["%s:%s" % (hostname, self.options.port)])
        except urllib2.URLError as e:
            if options.debug:
                print NGINX_CONN_ERR % e.reason
            return 2

        # Step 3: format & load data into container
        try:
            data = self._get_metrics(mc, hostname)
            zbx_container.add(data)
            zbx_container.add_item(hostname, "memcached.zbx_version", self.__version__)
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
    ret = MemcachedServer().run()
    print ret
    sys.exit(ret)