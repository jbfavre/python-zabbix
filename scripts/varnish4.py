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

class VarnishServer(protobix.SampleProbe):

    __version__ = '0.0.9'

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

    def _get_varnishstat(self):
        varnish_stats = simplejson.loads(
            check_output(
                ['varnishstat', '-n', socket.gethostname(), '-1', '-j']
            )
        )
        timestamp = int(time())
        return varnish_stats, timestamp

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( VarnishServer, self)._parse_args()

        # Varnish options
        general_options = optparse.OptionGroup(parser, "Varnish Configuration")
        general_options.add_option("-H", "--host", default="localhost",
                                   help="Varnish server hostname")
        general_options.add_option("-P", "--port", default=6379,
                                   help="Varnish server port")
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host

    def _get_metrics(self):
        """ Get Varnish stats and parse it """
        data = {}
        stats, timestamp = self._get_varnishstat(hostname)
        for (key, metric) in self.METRICS:
            data["varnish.%s" % key] = stats[metric]['value']
        data['varnish.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = VarnishServer().run()
    print ret
    sys.exit(ret)