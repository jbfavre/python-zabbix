#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Supervisord.
'''
import optparse
import socket
import subprocess
import simplejson
import re
import sys
import protobix


class SupervisorServer(protobix.SampleProbe):

    __version__ = '0.0.9'

    SUPERV_STAT_CHECK='sudo supervisorctl status'
    SUPERV_STATES = {
        'STOPPED': 0,
        'RUNNING': 0,
        'STOPPING': 1,
        'STARTING': 1,
        'EXITED': 2,
        'BACKOFF': 2,
        'FATAL': 2,
        'UNKNOWN': 2
    }

    def _get_infos(self):
        proc = subprocess.Popen(['/usr/bin/sudo', '/usr/bin/supervisorctl', 'status'], stdout=subprocess.PIPE)
        worker_list = {}
        for line in iter(proc.stdout.readline,''):
            proc_fullname = line.split()[0]
            group_name = proc_fullname.split(':')[0]
            proc_name = proc_fullname.split(':')[1]
            proc_name = re.sub('_\d+', '', proc_name)
            proc_status = line.split()[1]
            if group_name not in worker_list:
                worker_list[group_name] = {}
            if proc_name not in worker_list[group_name]:
                worker_list[group_name][proc_name] = {
                    'count': 0,
                    'STOPPED': 0,
                    'RUNNING': 0,
                    'STOPPING': 0,
                    'STARTING': 0,
                    'EXITED': 0,
                    'BACKOFF': 0,
                    'FATAL': 0,
                    'UNKNOWN': 0
                }
            worker_list[group_name][proc_name]['count'] += 1
            worker_list[group_name][proc_name][proc_status] += 1
        return worker_list

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( SupervisorServer, self)._parse_args()

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        self.hostname = socket.getfqdn()

    def _get_metrics(self):
        data = {}
        try:
            infos = self._get_infos()
            for group in infos:
                for worker in infos[group]:
                    for status in infos[group][worker]:
                        zbx_key = 'supervisord.worker[{0},{1},{2}]'
                        zbx_key = zbx_key.format(group, worker, status)
                        data[zbx_key] = infos[group][worker][status]
        except:
            print "CRITICAL: Could not get workers list"
            raise Exception('Fail to get supervisord infos')
        return data

    def _get_discovery(self):
        data = []
        try:
            infos = self._get_infos()
            for group in infos:
                for worker in infos[group]:
                    element = { '{#SPVGROUPNAME}': group,
                                '{#SPVWORKERNAME}': worker }
                    data.append(element)
        except:
            print "CRITICAL: Could not get workers list"
            raise Exception('Fail to get supervisord infos')
        return {'supervisord.workers.discovery': data}

if __name__ == '__main__':
    ret = SupervisorServer().run()
    print ret
    sys.exit(ret)