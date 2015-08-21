#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with varnishd using varnishstat.
    https://www.datadoghq.com/blog/how-to-monitor-varnish/
'''
import optparse
import socket
import protobix
import simplejson
import sys
from subprocess import check_output
from time import time, sleep

class VarnishServer():

    __version__ = '0.0.8'
    ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'
    METRICS = [
        ('cache[hit]', 'MAIN.cache_hit'),
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
        ('ban[completed]', 'MAIN.bans_completed'),
        ('client[dropped]', 'MAIN.sess_dropped'),
        ('client[queued]', 'MAIN.sess_queued'),
        ('object[nexpired]', 'MAIN.n_expired'),
        ('object[nlruexpired]', 'MAIN.n_lru_nuked'),
        ('thread[threads]', 'MAIN.threads'),
        ('thread[created]', 'MAIN.threads_created'),
        ('thread[failed]', 'MAIN.threads_failed'),
        ('thread[limited]', 'MAIN.threads_limited'),
        ('thread[queuelen]', 'MAIN.thread_queue_len')
    ]

    def _parse_args(self):
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

        return parser.parse_args()

    def _get_metrics(self, hostname):
        """ Get Varnish stats and parse it """
        data = {}
        data[hostname] = {}
        stats, timestamp = self._get_varnishstat(hostname)
        for (key, metric) in self.METRICS:
            data[hostname]["varnish.%s"%key] = stats[metric]['value']
        return data

    def _get_varnishstat(self,hostname):
        varnish_stats = simplejson.loads(check_output(['varnishstat', '-n', socket.gethostname(), '-1', '-j']))
        timestamp = int(time())
        return varnish_stats, timestamp

    def _init_container(self):
        zbx_container = protobix.DataContainer(
            data_type = 'items',
            zbx_host  = self.options.zabbix_server,
            zbx_port  = int(self.options.zabbix_port),
            debug     = self.options.debug,
            dryrun    = self.options.dry
        )
        zbx_container.data_type = 'items'
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
            data = self._get_metrics(hostname)
        except:
            return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
            zbx_container.add_item(hostname, "varnish.zbx_version", self.__version__)
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
    ret = VarnishServer().run()
    print ret
    sys.exit(ret)