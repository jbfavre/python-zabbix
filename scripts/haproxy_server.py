#!/usr/bin/python
# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import socket
import csv
import optparse
import protobix
import select
import sys

from time import time
from traceback import format_exc

class TimeoutException(Exception):
    pass

class HAProxyServer(protobix.SampleProbe):

    __version__ = '0.0.9'

    def _get_options(self, v):
        options = {'1.3': (
            {'hap_proxy_name': False},
            {'hap_sv_name': False},
            {'hap_qcur': True},
            {'hap_qmax': True},
            {'hap_scur': True},
            {'hap_smax': True},
            {'hap_slim': False},
            {'hap_stot': True},
            {'hap_bin': True},
            {'hap_bout': True},
            {'hap_dreq': False},
            {'hap_dresp': False},
            {'hap_ereq': False},
            {'hap_econ': False},
            {'hap_eresp': False},
            {'hap_wretr': False},
            {'hap_wredis': False},
            {'hap_status': True},
            {'hap_weight': False},
            {'hap_act': False},
            {'hap_bck': False},
            {'hap_chkfail': False},
            {'hap_chkdown': False},
            {'hap_lastchg': False},
            {'hap_downtime': False},
            {'hap_qlimit': False},
            {'hap_pid': False},
            {'hap_iid': False},
            {'hap_sid': False},
            {'hap_throttle': False},
            {'hap_lbtot': False},
            {'hap_tracked': False},
            {'hap_type': False},
            {'hap_rate': False},
            {'hap_rate_lim': False},
            {'hap_rate_max': False},
            {'Null': False},
            ), '1.4': (
            {'hap_proxy_name': False},
            {'hap_sv_name': False},
            {'hap_qcur': True},
            {'hap_qmax': True},
            {'hap_scur': True},
            {'hap_smax': True},
            {'hap_slim': False},
            {'hap_stot': True},
            {'hap_bin': True},
            {'hap_bout': True},
            {'hap_dreq': False},
            {'hap_dresp': False},
            {'hap_ereq': True},
            {'hap_econ': True},
            {'hap_eresp': True},
            {'hap_wretr': False},
            {'hap_wredis': False},
            {'hap_status': True},
            {'hap_weight': False},
            {'hap_act': False},
            {'hap_bck': False},
            {'hap_chkfail': False},
            {'hap_chkdown': False},
            {'hap_lastchg': False},
            {'hap_downtime': False},
            {'hap_qlimit': False},
            {'hap_pid': False},
            {'hap_iid': False},
            {'hap_sid': False},
            {'hap_throttle': False},
            {'hap_lbtot': False},
            {'hap_tracked': False},
            {'hap_type': False},
            {'hap_rate': False},
            {'hap_rate_lim': False},
            {'hap_rate_max': False},
            {'hap_check_status': True},
            {'hap_check_code': True},
            {'hap_check_duration': True},
            {'hap_hrsp_1xx': True},
            {'hap_hrsp_2xx': True},
            {'hap_hrsp_3xx': True},
            {'hap_hrsp_4xx': True},
            {'hap_hrsp_5xx': True},
            {'hap_hrsp_other': True},
            {'hap_hanafail': False},
            {'hap_req_rate': False},
            {'hap_req_rate_max': False},
            {'hap_req_tot': False},
            {'hap_cli_abrt': False},
            {'hap_srv_abrt': False},
            {'Null': False},
            ), '1.5': (
            {'pxname': False},
            {'svname': False},
            {'qcur': True},
            {'qmax': True},
            {'scur': True},
            {'smax': True},
            {'slim': False},
            {'stot': True},
            {'bin': True},
            {'bout': True},
            {'dreq': False},
            {'dresp': False},
            {'ereq': True},
            {'econ': True},
            {'eresp': True},
            {'wretr': False},
            {'wredis': False},
            {'status': True},
            {'weight': False},
            {'act': False},
            {'bck': False},
            {'chkfail': False},
            {'chkdown': False},
            {'lastchg': False},
            {'downtime': False},
            {'qlimit': False},
            {'pid': False},
            {'iid': False},
            {'sid': False},
            {'throttle': False},
            {'lbtot': False},
            {'tracked': False},
            {'type': False},
            {'rate': False},
            {'rate_lim': False},
            {'rate_max': False},
            {'check_status': True},
            {'check_code': True},
            {'check_duration': True},
            {'hrsp_1xx': True},
            {'hrsp_2xx': True},
            {'hrsp_3xx': True},
            {'hrsp_4xx': True},
            {'hrsp_5xx': True},
            {'hrsp_other': True},
            {'hanafail': False},
            {'req_rate': False},
            {'req_rate_max': False},
            {'req_tot': False},
            {'cli_abrt': False},
            {'srv_abrt': False},
            {'comp_in': False},
            {'comp_out': False},
            {'comp_byp': False},
            {'comp_rsp': False},
            {'lastsess': False},
            {'last_chk': False},
            {'last_agt': False},
            {'qtime': False},
            {'ctime': False},
            {'rtime': False},
            {'ttime': False},
            {'Null': False},
            )}

        return options[v[:3]]

    def _cmd_exec(self, command, timeout=200):
        """ Executes a HAProxy command by sending a message to a HAProxy's local
    UNIX socket and waiting up to 'timeout' milliseconds for the response.
    """

        buffer = ''
        socket.setdefaulttimeout(3)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(self.socket_name)
        client.send(command + '\n')
        output = client.recv(8192)
        while output:
            buffer += output.decode('ASCII')
            output = client.recv(8192)

        client.close()
        return buffer

    def _get_version(self):
        buffer = self._cmd_exec(command='show info')
        buffer = buffer.strip()
        lines = buffer.split('\n')
        self.info = dict(row.strip().split(':', 1) for row in lines)
        return self.info['Version'].strip()

    def _get_data(self):

        def get_output_key(index):
            return index.keys()[0]

        hap_version = self._get_version()
        buffer = self._cmd_exec('show stat')
        buffer = buffer.lstrip('# ')
        csv_stat = csv.DictReader(buffer.split(',\n'))
        data = {}
        for row in csv_stat:
            if row['pxname'] not in data:
                data[row['pxname']] = {}
            if row['svname'] in ['FRONTEND']:
                options_list = self._get_options(hap_version)
                pool_stats = {}
                for i in range(0, len(options_list)):
                    key = get_output_key(options_list[i])
                    if options_list[i][key] is True:
                        pool_stats[key] = row[key]
                data[row['pxname']] = pool_stats
        return data

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host
        self.socket_name = self.options.socket
        self.discovery_key = 'haproxy_server.pools.discovery'

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( HAProxyServer, self)._parse_args()

        # HaProxy options
        haproxy_options = optparse.OptionGroup(parser, 'Haproxy Configuration')
        haproxy_options.add_option('-H', '--host', default='localhost',
                                   help='Haproxy server hostname')
        haproxy_options.add_option('-P', '--port', default=1936,
                                   help='Haproxy stats port')
        haproxy_options.add_option('-s', '--socket',
                                   default='/run/haproxy.socket',
                                   help='Haproxy stats port')
        haproxy_options.add_option('--username', default='zabbix',
                                   help='Haproxy stats username')
        haproxy_options.add_option('--password', default='zabbix',
                                   help='Haproxy stats password')
        haproxy_options.add_option('--uri', default='',
                                   help='Haproxy stats URI')
        parser.add_option_group(haproxy_options)
        (options, args) = parser.parse_args()
        return (options, args)

    def _get_discovery(self):
        raw_data = self._get_data()
        data = {self.discovery_key: []}
        for pxname in raw_data:
            element = {'{#HAPPOOLNAME}': pxname}
            data[self.discovery_key].append(element)
        return { self.hostname: data }

    def _get_metrics(self):
        raw_data = self._get_data()
        data = {}
        for pxname in raw_data:
            for metric in raw_data[pxname]:
                if raw_data[pxname][metric] == '':
                    raw_data[pxname][metric] = 0
                if metric == 'status' and raw_data[pxname][metric] \
                    == 'OPEN':
                    raw_data[pxname][metric] = 1
                elif metric == 'status':
                    raw_data[pxname][metric] = 0
                zbx_key = 'haproxy_server.pool[{0},{1}]'
                zbx_key = zbx_key.format(pxname, metric)
                data[zbx_key] = raw_data[pxname][metric]
        data['haproxy_server.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = HAProxyServer().run()
    print((ret))
    sys.exit(ret)