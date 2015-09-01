#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Redis.
'''
import optparse
import socket
import sys
import protobix
import redis

class RedisServer(protobix.SampleProbe):

    __version__ = '0.0.9'

    REDIS_REPROLE_MAPPING={'master':1,'slave':0}
    REDIS_REPSTATE_MAPPING={'up':1,'down':0}

    def _get_data_from_dict(self, result, prefix):
        data = {}
        for key, value in result.iteritems():
            if isinstance(value, dict):
                data.update(
                    self._get_data_from_dict(value, "%s%s," % (prefix, key))
                )
            else:
                data.update({ "%s%s]" % (prefix, key): value})
        return data

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( RedisServer, self)._parse_args()

        general_options = optparse.OptionGroup(parser, "Redis Configuration")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="Redis server hostname")
        general_options.add_option("-P", "--port", default=6379,
                                   help="Redis server port")
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            hostname = socket.getfqdn()
        else:
            hostname = self.options.host
        self.redis = redis.StrictRedis(
            host=self.options.host,
            port=self.options.port,
            db="",
            password="",
            socket_timeout=1
        )

    def _get_discovery(self, hostname):
        """ Discover 'dynamic' items like
            http://redis.io/commands/info
            replication: depends on slave number
            cluster: empty if not applicable
            keyspace: depends on database number
        """
        data = {}
        section_list = { 'keyspace': 'REDISDB' }
        data = { "redis.cluster.discovery":[] }
        for section, lldvalue in section_list.iteritems():
            data["redis.%s.discovery" % section] = []
            result = self.redis.info(section)
            print result
            if result == {}: result = {}
            for key, value in result.iteritems():
                dsc_data = {"{#%s}" % lldvalue: "%s" % key }
                data[("redis.%s.discovery" % (section))].append(dsc_data)
        return { hostname: data }

    def _get_metrics(self, hostname):
        """ http://redis.io/commands/info
            server: General information about the Redis server
            clients: Client connections section
            memory: Memory consumption related information
            persistence: RDB and AOF related information
            stats: General statistics
            replication: Master/slave replication information
            cpu: CPU consumption statistics
            commandstats: Redis command statistics
            cluster: Redis Cluster section
            keyspace: Database related statistics
        """
        data = {}
        section_list = [ 'server', 'clients', 'memory', 'persistence',
                         'stats', 'replication', 'cpu', 'cluster', 'keyspace' ]
        for section in section_list:
            result = self.redis.info(section)
            data.update(
                self._get_data_from_dict(result, ("redis.%s[" % section))
            )
        if data['redis.replication[role]'] == 'master':
            data['redis.replication[master_last_io_seconds_ago]'] = 0
            data['redis.replication[master_link_status]'] = 'up'
            data['redis.replication[master_sync_in_progress]'] = 0
        data['redis.zbx_version'] = self.__version__
        return { hostname: data }

if __name__ == '__main__':
    ret = RedisServer().run()
    print ret
    sys.exit(ret)