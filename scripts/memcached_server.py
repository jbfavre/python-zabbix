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

class MemcachedServer(protobix.SampleProbe):

    __version__="0.0.9"

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( MemcachedServer, self)._parse_args()

        # Memcached options
        general_options = optparse.OptionGroup(parser, "Memcache Configuration")
        general_options.add_option("-H", "--host", default="localhost",
                                   help="Memcache server hostname")
        general_options.add_option("-P", "--port", default=11211,
                                   help="Memcache server port")
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host
        self.memcached = memcache.Client(
            ["%s:%s" % (self.hostname, self.options.port)]
        )

    def _get_metrics(self, hostname):
        data = {}
        data[hostname] = {}
        ''' FIXME
            add support for:
                * stats slabs
                * stats items
                * stats sizes <= /!\ lock memcached /!\
        '''
        result = self.memcached.get_stats()
        for node_stats in result:
            server, stats = node_stats
            host = server.split(':')[0]
            if not host in data:
                data[host] = {}
            for stat in stats:
                data[host]["memcached.%s"%stat] = stats[stat]
        data[hostname]['memcached.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = MemcachedServer().run()
    print ret
    sys.exit(ret)