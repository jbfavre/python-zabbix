#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Cloudera Manager via the CM API.
'''
import optparse
import json
import socket
import subprocess
import xmltodict
import simplejson
import sys

import protobix

class PacemakerCluster(protobix.SampleProbe):

    __version__ = '0.0.9'

    class Nodes(object):
        def __init__(self, nodes_status):
            self.status = nodes_status

        def _get_metrics(self):
            data = {}
            nb_configured = 0
            for node in self.status:
                nb_configured += 1
                zbx_key = 'pacemaker.nodes[{0}]'
                for  key in ['online', 'standby', 'standby_onfail', 'pending',
                             'unclean', 'shutdown', 'expected_up']:
                    real_key = zbx_key.format(key)
                    if real_key not in data:
                        data[real_key] = 0
                    if node['@'+key] == 'true':
                        data[real_key] += 1
            data['pacemaker.nodes[configured]'] = nb_configured
            return data

        def _get_discovery(self):
            zbx_key = 'pacemaker.nodes.discovery'
            data = {
                zbx_key: []
            }
            for node in self.status:
                data[zbx_key].append({ '{#PCMKNODE}': node['@name'] })
            return data

    class Resources(object):
        def __init__(self, resources_status):
            self.status = resources_status

        def _get_metrics(self):
            data = {}
            nb_configured = 0
            zbx_key = 'pacemaker.resources[{0}]'
            if 'resource' in self.status:
                for resource in self.status['resource']:
                  nb_configured += 1
                  for key in ['active', 'orphaned', 'managed', 'failed',
                              'failure_ignored']:
                    real_key = zbx_key.format(key)
                    if real_key not in data:
                        data[real_key] = 0
                    if resource['@'+key] == 'true':
                        data[real_key] += 1
            if 'clone' in self.status:
                for resource in self.status['clone']['resource']:
                    nb_configured += 1
                    for key in ['active', 'orphaned', 'managed', 'failed',
                                'failure_ignored']:
                        real_key = zbx_key.format(key)
                        if real_key not in data:
                            data[real_key] = 0
                        if resource['@'+key] == 'true':
                            data[real_key] += 1
            data['pacemaker.resources[configured]'] = nb_configured
            return data

        def _get_discovery(self):
            return false
            zbx_key = 'pacemaker.resources.discovery'
            data = {
              zbx_key: []
            }
            for resource in self.status:
                data[zbx_key].append({ '{#PCMKRESOURCE}': resource['@id'] })
            return data

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( PacemakerCluster, self)._parse_args()

        (options, args) = parser.parse_args()
        return parser.parse_args()

    def _init_probe(self):
        self.hostname = socket.getfqdn()
        process = subprocess.Popen('sudo /usr/sbin/crm_mon -1 -X -r -f',
                                    shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        out, err = process.communicate()
        status = xmltodict.parse(out)['crm_mon']
        self.nodes=self.Nodes(status["nodes"]["node"])
        self.resources=self.Resources(status["resources"])
        self.status=status["summary"]

    def _get_metrics(self):
        data = {}
        zbx_key = 'pacemaker.cluster.{0}'
        real_key = zbx_key.format('master')
        is_master = 1
        if self.hostname != self.status['current_dc']['@name']:
          is_master = 0
        data[real_key] = is_master
        real_key = zbx_key.format('with_quorum')
        with_quorum = 1
        if self.status['current_dc']['@with_quorum'] == 'false':
          with_quorum = 0
        data[real_key] = with_quorum
        real_key = zbx_key.format('expected_votes')
        data[real_key] = int(self.status['nodes_configured']['@expected_votes'])
        real_key = zbx_key.format('resources_configured')
        data[real_key] = int(self.status['resources_configured']['@number'])
        data.update(self.nodes._get_metrics())
        data.update(self.resources._get_metrics())
        data['pacemaker.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = PacemakerCluster().run()
    print ret
    sys.exit(ret)
