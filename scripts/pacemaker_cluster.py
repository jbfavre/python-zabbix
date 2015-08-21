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

class PacemakerCluster(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

    def _get_metrics(self, hostname):
        data = {}
        zbx_key = 'pacemaker.cluster.{0}'
        real_key = zbx_key.format('master')
        is_master = 1
        if hostname != self.status['current_dc']['@name']:
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
        return data

    def _get_discovery(self,hostname):
        return false
        data = {}
        data.update(self.nodes._get_discovery())
        data.update(self.resources._get_discovery())
        return data

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
        ''' Parse the script arguments'''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs Pacemaker call but do not send "
                                   "anything to the Zabbix server. Can be used "
                                   "for Update mode")
        parser.add_option("-D", "--debug", action="store_true",
                          help="Enable debug mode. This will prevent bulk send "
                               "operations and force sending items one after the "
                               "other, displaying result for each one")
        parser.add_option("-v", "--verbose", action="store_true",
                          help="When used with debug option, will force value "
                               "display for each items managed.")

        mode_group = optparse.OptionGroup(parser, "Program Mode")
        mode_group.add_option("--update-items", action="store_const",
                              dest="mode", const="update_items",
                              help="Get & send items to Zabbix. This is the default "
                                   "behaviour even if option is not specified")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

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
        hostname = socket.getfqdn()

        # Step 1: init container
        try:
            zbx_container = self._init_container()
        except:
            return 1

        # Step 2: get data
        try:
            process = subprocess.Popen('sudo /usr/sbin/crm_mon -1 -X -r -f',
                                        shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            out, err = process.communicate()
            status = xmltodict.parse(out)['crm_mon']
            self.nodes=self.Nodes(status["nodes"]["node"])
            self.resources=self.Resources(status["resources"])
            self.status=status["summary"]

            data = {}
            zbx_container.set_type("items")
            data[hostname] = self._get_metrics(hostname)
        except:
            return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
            zbx_container.add_item(hostname, "pacemaker.zbx_version", self.__version__)
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
    ret = PacemakerCluster().run()
    print ret
    sys.exit(ret)