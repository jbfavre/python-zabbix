#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with memcached.
'''
import optparse
import platform
import sys
import protobix
import memcache

__version__="0.0.1"

ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
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

    (options, args) = parser.parse_args()

    """if options.mode == "update_items":
        required.append("zabbix_server")"""

    return (options, args)

def get_discovery(memcache, hostname):
    """ Discover 'dynamic' items like
        http://redis.io/commands/info
        replication: depends on slave number
        cluster: empty if not applicable
        keyspace: depends on database number
    """
    data = {}
    data[hostname] = {}
    return data

def get_metrics(memcache, hostname):
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

def main():
    (options, args) = parse_args()

    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    try:
        mc = memcache.Client(["%s:%s" % (hostname, options.port)])
    except:
        return 1

    zbx_container = protobix.DataContainer()
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data = get_metrics(mc, hostname)

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data = get_discovery(mc, hostname)

    zbx_container.add(data)
    zbx_container.add_item(hostname, "memcached.zbx_version", __version__)

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

