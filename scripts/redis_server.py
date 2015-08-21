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

class RedisServer(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

    REDIS_REPROLE_MAPPING={'master':1,'slave':0}
    REDIS_REPSTATE_MAPPING={'up':1,'down':0}

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs Redis call but do not send "
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
                                   "Discovery on Redis. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

        general_options = optparse.OptionGroup(parser, "Redis Configuration")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="Redis server hostname")
        general_options.add_option("-p", "--port", help="Redis server port",
                                   default=6379)
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

    def _get_discovery(self, hostname):
        """ Discover 'dynamic' items like
            http://redis.io/commands/info
            replication: depends on slave number
            cluster: empty if not applicable
            keyspace: depends on database number
        """
        data = {}
        data[hostname] = {}
        section_list = { 'keyspace': 'REDISDB' }
        data[hostname] = { "redis.cluster.discovery":[] }
        for section, lldvalue in section_list.iteritems():
            data[hostname]["redis.%s.discovery" % section] = []
            result = self.redis.info(section)
            for key, value in result.iteritems():
                dsc_data = {"{#%s}" % lldvalue: "%s" % key }
                data[hostname][("redis.%s.discovery" % (section))].append(dsc_data)
        return data

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
        data[hostname] = {}
        section_list = [ 'server', 'clients', 'memory', 'persistence',
                         'stats', 'replication', 'cpu', 'cluster', 'keyspace' ]
        for section in section_list:
            result = self.redis.info(section)
            data[hostname].update(self._get_data_from_dict(result, ("redis.%s[" % section)))
        return data

    def _get_data_from_dict(self, result, prefix):
        data = {}
        for key, value in result.iteritems():
            if isinstance(value, dict):
                data.update(self._get_data_from_dict(value, "%s%s," % (prefix, key)))
            else:
                data.update({ "%s%s]" % (prefix, key): value})
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
        except:
            return 1

        # Step 2: get data
        try:
            self.redis = redis.StrictRedis(
                host=self.options.host,
                port=self.options.port,
                db="",
                password="",
                socket_timeout=1
            )
            if self.options.mode == "update_items":
                zbx_container.set_type("items")
                data = self._get_metrics(hostname)
                '''
                    do value mapping to avoid text itms
                '''
                #key = 'redis.replication[role]'
                #data[hostname][key] = \
                #    self.REDIS_REPROLE_MAPPING[data[hostname][key]]
                #key = 'redis.replication[master_link_status]'
                #data[hostname][key] = \
                #    self.REDIS_REPSTATE_MAPPING[data[hostname][key]]
                '''
                    provide fake data for master
                    to avoid NOT SUPPORTED items
                '''
                if data[hostname]['redis.replication[role]'] == 'master':
                    data[hostname]['redis.replication[master_last_io_seconds_ago]'] = 0
                    data[hostname]['redis.replication[master_link_status]'] = 'up'
                    data[hostname]['redis.replication[master_sync_in_progress]'] = 0
                zbx_container.add_item(hostname, "redis.zbx_version", self.__version__)
            elif self.options.mode == "discovery":
                zbx_container.set_type("lld")
                data = self._get_discovery(hostname)
        except:
            return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
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
    ret = RedisServer().run()
    print ret
    sys.exit(ret)
