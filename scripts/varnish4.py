#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with varnishd using varnishstat.
'''
import optparse
import socket
import protobix
import simplejson
from subprocess import check_output
from time import time, sleep

__version__="0.0.1"

REDIS_REPROLE_MAPPING={'master':1,'slave':0}

ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
    ''' Parse the script arguments
    '''
    parser = optparse.OptionParser()

    parser.add_option("-d", "--dry", action="store_true",
                          help="Performs Varnish call but do not send "
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
                               "Discovery on Varnish. "
                               "Default is to get & send items")
    parser.add_option_group(mode_group)
    parser.set_defaults(mode="update_items")

    general_options = optparse.OptionGroup(parser, "Varnish Configuration")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="Varnish server hostname")
    general_options.add_option("-p", "--port", help="Varnish server port",
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

    return (options, args)

def get_discovery(hostname):
    """ Discover 'dynamic' items like backend """
    data = {}
    data[hostname] = {}

    return data

def get_metrics(hostname):
    """ Get Varnish stats and parse it """
    data = {}
    data[hostname] = {}
    stats, timestamp = get_varnishstat(hostname)
    metrics = [('cache[hit]', 'MAIN.cache_hit'),
               ('cache[hitpass]', 'MAIN.cache_hitpass'),
               ('cache[miss]', 'MAIN.cache_miss'),
               ('backend[conn]', 'MAIN.backend_conn'),
               ('backend[unhealthy]', 'MAIN.backend_unhealthy'),
               ('backend[busy]', 'MAIN.backend_busy'),
               ('backend[fail]', 'MAIN.backend_fail'),
               ('backend[reuse]', 'MAIN.backend_reuse'),
               ('backend[toolate]', 'MAIN.backend_toolate'),
               ('backend[recycle]', 'MAIN.backend_recycle'),
               ('backend[retry]', 'MAIN.backend_retry'),
               ('backend[req]', 'MAIN.backend_req'),
               ('client[conn]', 'MAIN.sess_conn'),
               ('client[drop]', 'MAIN.sess_drop'),
               ('client[req]', 'MAIN.client_req'),
               ('client[hdrbytes]', 'MAIN.s_req_hdrbytes'),
               ('client[bodybytes]', 'MAIN.s_req_bodybytes'),
               ('object[head]', 'MAIN.n_objecthead'),
               ('object[num]', 'MAIN.n_object'),
               ('ban[count]', 'MAIN.bans'),
               ('ban[completed]', 'MAIN.bans_completed')]

    for (key, metric) in metrics:
        data[hostname]["varnish.%s"%key] = stats[metric]['value']

    return data

def get_varnishstat(hostname):
    varnish_stats = simplejson.loads(check_output(['varnishstat', '-n', socket.gethostname(), '-1', '-j']))
    timestamp = int(time())
    return varnish_stats, timestamp

def main():
    (options, args) = parse_args()

    if options.host == 'localhost':
        hostname = socket.getfqdn()
    else:
        hostname = options.host

    zbx_container = protobix.DataContainer()
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data = get_metrics(hostname)

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data = get_discovery(r, hostname)

    zbx_container.add(data)
    zbx_container.add_item(hostname, "varnish.zbx_version", __version__)

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

