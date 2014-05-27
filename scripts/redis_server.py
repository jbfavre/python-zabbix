#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Cloudera Manager via the CM API.
'''
import optparse
import platform
import protobix
import redis

__version__="0.0.1"

REDIS_REPROLE_MAPPING={'master':1,'slave':0}

ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
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

    (options, args) = parser.parse_args()

    """if options.mode == "update_items":
        required.append("zabbix_server")"""

    return (options, args)

def get_discovery(redis, hostname):
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
        result = redis.info(section)
        for key, value in result.iteritems():
            dsc_data = {"{#%s}" % lldvalue: "%s" % key }
            data[hostname][("redis.%s.discovery" % (section))].append(dsc_data)
    return data

def get_metrics(redis, hostname):
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
        result = redis.info(section)
        data[hostname].update(get_data_from_dict(result, ("redis.%s[" % section)))
    return data

def get_data_from_dict(result, prefix):
    data = {}
    for key, value in result.iteritems():
        if isinstance(value, dict):
            data.update(get_data_from_dict(value, "%s%s," % (prefix, key)))
        else:
            data.update({ "%s%s]" % (prefix, key): value})
    return data

def main():
    (options, args) = parse_args()

    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    try:
        r = redis.StrictRedis(host=options.host, port=options.port, db="", password="", socket_timeout=0.5)
    except:
        return 1

    zbx_container = protobix.DataContainer()
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data = get_metrics(r, hostname)
        '''
            provide fake data for master
            to avoid NOt SUPPORTED items
        '''
        if data[hostname]['redis.replication[role]'] == 'master':
            data[hostname]['redis.replication[master_last_io_seconds_ago]'] = 0
            data[hostname]['redis.replication[master_link_status]'] = 'up'
            data[hostname]['redis.replication[master_sync_in_progress]'] = 0

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data = get_discovery(r, hostname)

    zbx_container.add(data)
    zbx_container.add_item(hostname, "redis.zbx_version", __version__)

    zbx_container.set_host(options.zabbix_server)
    zbx_container.set_port(int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)
    zbx_container.set_dryrun(options.dry)

    try:
        zbxret = zbx_container.send(zbx_container)
    except protobix.SenderException as zbx_e:
        if options.debug:
            print ZBX_CONN_ERR % zbx_e.err_text
        return 2
    else:
        return 0

if __name__ == "__main__":
    ret = main()
    print ret

