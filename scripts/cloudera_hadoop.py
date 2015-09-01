#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Cloudera Manager via the CM API.
'''
import sys
import socket
import logging
import simplejson
import optparse
import tempfile
import struct
from datetime import datetime, timedelta
from os import getcwd, devnull
from os.path import join, isfile
from subprocess import call
from time import sleep, time
from urllib2 import quote

import cm_api.endpoints.clusters
import cm_api.endpoints.hosts
import cm_api.endpoints.services
import cm_api.endpoints.roles
import cm_api.endpoints.cms
from cm_api.api_client import get_root_resource, ApiException
from cm_api.endpoints.roles import get_all_roles

import protobix

class ClouderaHadoop(protobix.SampleProbe):

    __version__="0.0.9"
    CM_API_VERSION = 5
    CM_COMMISSION_MAPPING = { 'UNKNOWN': -1,
                              'COMMISSIONED': 0,
                              'DECOMMISSIONING': 1,
                              'DECOMMISSIONED': 2 }
    CM_HEALTH_MAPPING = { 'HISTORY_NOT_AVAILABLE': -1,
                          'NOT_AVAILABLE': -1,
                          'DISABLED': -1,
                          'GOOD': 0,
                          'CONCERNING': 1,
                          'BAD': 2 }
    CM_SERVICE_MAPPING = { 'HISTORY_NOT_AVAILABLE': -1,
                           'UNKNOWN': -1,
                           'STARTING': 0,
                           'STARTED': 0,
                           'STOPPING': 1,
                           'STOPPED': 1,
                           'NA': 0 }
    CM_BOOLEAN_MAPPING = { 'False': 0,
                           'True': 1 }

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( ClouderaHadoop, self)._parse_args()

        # Cloudera Manager API options
        cmapi_options = optparse.OptionGroup(parser, 'Hadoop Cloudera Manager API Configuration')
        cmapi_options.add_option('-H', '--host', metavar='HOST', default='127.0.0.1',
                                 help='Hadoop Cloudera Manager API hostname')
        cmapi_options.add_option('-P', '--port', default = None,
                                 help='Hadoop Cloudera Manager API port')
        cmapi_options.add_option('--use-tls', action='store_true', default = False,
                                 help='If specified, force TLS use. Default is NO')
        parser.add_option_group(cmapi_options)

        (options, args) = parser.parse_args()
        required = ['host', 'config']
        for required_opt in required:
            if getattr(options, required_opt) is None:
                parser.error("Please specify the required argument: --%s" %
                             (required_opt.replace('_','-'),))
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host
        (username, password) = open(self.options.config, 'r').readline().rstrip('\n').split(':')
        self.cdh_api = get_root_resource(
            self.options.host,
            self.options.port,
            username,
            password,
            self.options.use_tls,
            self.CM_API_VERSION
        )
        return {'username': username, 'password': password}

    def _get_discovery(self):
        mgmt_hostname = self.hostname
        data = {}

        for cluster in self.cdh_api.get_all_clusters():
            if not mgmt_hostname in data:
                data[mgmt_hostname] = {
                    'hadoop.cm.cluster.discovery': [],
                    'hadoop.cm.cluster.check.discovery': [],
                    'hadoop.cm.host.discovery': [],
                    'hadoop.cm.host.check.discovery': [],
                    'hadoop.cm.role.discovery': [],
                    'hadoop.cm.role.check.discovery': [],
                    'hadoop.cm.service.discovery': [],
                    'hadoop.cm.service.check.discovery': []
                }

            for instance in cluster.list_hosts():
                host = self.cdh_api.get_host(instance.hostId)
                data[host.hostname] = {
                    'hadoop.cm.cluster.discovery': [],
                    'hadoop.cm.cluster.check.discovery': [],
                    'hadoop.cm.host.discovery': [],
                    'hadoop.cm.host.check.discovery': [],
                    'hadoop.cm.role.discovery': [],
                    'hadoop.cm.role.check.discovery': [],
                    'hadoop.cm.service.discovery': [],
                    'hadoop.cm.service.check.discovery': []
                }

                host_list = {'{#HDPCLUSTERNAME}': ("%s" % cluster.name) }
                key = 'hadoop.cm.host.discovery'
                data[host.hostname][key].append(host_list)

                for check in host.healthChecks:
                    check_list = {
                        '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                        '{#HDPHOSTCHECKNAME}': ("%s" % check['name'].lower())
                    }
                    key = 'hadoop.cm.host.check.discovery'
                    data[host.hostname][key].append(check_list)

            for service in cluster.get_all_services(view="full"):
                service_list = {
                    '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                    '{#HDPSERVICENAME}': ("%s" % service.type.lower())
                }
                key = 'hadoop.cm.service.discovery'
                data[mgmt_hostname][key].append(service_list)

                for check in service.healthChecks:
                    check_list = {
                        '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                        '{#HDPSERVICENAME}': ("%s" % service.type.lower()),
                        '{#HDPSERVICECHECKNAME}': ("%s" % check['name'].lower())
                    }
                    key = 'hadoop.cm.service.check.discovery'
                    data[mgmt_hostname][key].append(check_list)

                for role in service.get_all_roles(view="full"):
                    host = self.cdh_api.get_host(instance.hostId)
                    role_list = {
                        '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                        '{#HDPSERVICENAME}': ("%s" % service.type.lower()),
                        '{#HDPROLENAME}': ("%s" % role.type.lower())
                    }
                    key = 'hadoop.cm.role.discovery'
                    data[host.hostname][key].append(role_list)

                    for check in role.healthChecks:
                        check_list = {
                            '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                            '{#HDPSERVICENAME}': ("%s" % service.type.lower()),
                            '{#HDPROLENAME}': ("%s" % role.type.lower()),
                            '{#HDPROLECHECKNAME}': ("%s" % check['name'].lower())
                        }
                        key = 'hadoop.cm.role.check.discovery'
                        data[host.hostname][key].append(check_list)

            cluster_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name) }
            key = 'hadoop.cm.cluster.discovery'
            data[mgmt_hostname][key].append(cluster_list)

        mgmt_service = self.cdh_api.get_cloudera_manager().get_service()
        service_list = {
            '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
            '{#HDPSERVICENAME}': ("%s" % mgmt_service.type.lower())
        }
        key = 'hadoop.cm.service.discovery'
        data[mgmt_hostname][key].append(service_list)

        for check in mgmt_service.healthChecks:
            check_list = {
                '{#HDPCLUSTERNAME}': ("%s" % cluster.name),
                '{#HDPSERVICENAME}': ("%s" % mgmt_service.type.lower()),
                '{#HDPSERVICECHECKNAME}': ("%s" % check['name'].lower())
            }
            key = 'hadoop.cm.service.check.discovery'
            data[mgmt_hostname][key].append(check_list)

        return data

    def _get_metrics(self):
        mgmt_hostname = self.hostname
        data = {}

        for cluster in self.cdh_api.get_all_clusters():
            if not mgmt_hostname in data:
                data[mgmt_hostname] = {}

            key = "hadoop.cm.cluster[%s,version]"
            data[mgmt_hostname][(key % cluster.name)] =  cluster.version
            key = "hadoop.cm.cluster[%s,maintenanceMode]"
            data[mgmt_hostname][(key % cluster.name)] = self.CM_BOOLEAN_MAPPING[str(cluster.maintenanceMode)]
            for instance in cluster.list_hosts():
                host = self.cdh_api.get_host(instance.hostId)
                if not host.hostname in data:
                    data[host.hostname] = {}

                key = "hadoop.cm.host[%s,maintenanceMode]"
                data[host.hostname][( key % cluster.name)] = self.CM_BOOLEAN_MAPPING[str(host.maintenanceMode)]
                key = "hadoop.cm.host[%s,healthSummary]"
                data[host.hostname][(key % cluster.name)] = self.CM_HEALTH_MAPPING[str(host.healthSummary)]
                key = "hadoop.cm.host[%s,commissionState]"
                data[host.hostname][(key % cluster.name)] = self.CM_COMMISSION_MAPPING[str(host.commissionState)]
                difference = datetime.now() - host.lastHeartbeat
                differenceTotalSeconds = (difference.microseconds + (difference.seconds + difference.days*24*3600) * 1e6) / 1e6
                key = "hadoop.cm.host[%s,lastHeartbeat]"
                data[host.hostname][(key % cluster.name)] = differenceTotalSeconds
                ''' Only works with Python 2.7
                   differenceTotalSeconds = (datetime.now() - host.lastHeartbeat).total_seconds()
                   data[host.hostname][("hadoop.cm.host[%s,lastHeartbeat]" % cluster.name)] = differenceTotalSeconds'''
                for check in host.healthChecks:
                    key = "hadoop.cm.host.check[%s,%s]"
                    data[host.hostname][(key % (cluster.name, check['name'].lower()))] = self.CM_HEALTH_MAPPING[check['summary']]

            for service in cluster.get_all_services(view="full"):
                key = "hadoop.cm.service[%s,%s,serviceState]"
                data[mgmt_hostname][(key % ( cluster.name, service.type.lower()))] = self.CM_SERVICE_MAPPING[service.serviceState]
                key = "hadoop.cm.service[%s,%s,healthSummary]"
                data[mgmt_hostname][(key % ( cluster.name, service.type.lower()))] = self.CM_HEALTH_MAPPING[service.healthSummary]
                key = "hadoop.cm.service[%s,%s,configStale]"
                data[mgmt_hostname][(key % ( cluster.name, service.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(service.configStale)]
                key = "hadoop.cm.service[%s,%s,maintenanceMode]"
                data[mgmt_hostname][(key % ( cluster.name, service.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(service.maintenanceMode)]

                for check in service.healthChecks:
                    key = "hadoop.cm.service.check[%s,%s,%s,checkSummary]"
                    data[mgmt_hostname][(key % ( cluster.name, service.type.lower(), check['name'].lower()))] = self.CM_HEALTH_MAPPING[check['summary']]

                for role in service.get_all_roles(view="full"):
                    host = self.cdh_api.get_host(role.hostRef.hostId)
                    key = "hadoop.cm.role[%s,%s,%s,commissionState]"
                    data[host.hostname][(key % ( cluster.name, service.type.lower(), role.type.lower()))] = self.CM_COMMISSION_MAPPING[str(role.commissionState)]
                    key = "hadoop.cm.role[%s,%s,%s,configStale]"
                    data[host.hostname][(key % ( cluster.name, service.type.lower(), role.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(role.configStale)]
                    key = "hadoop.cm.role[%s,%s,%s,healthSummary]"
                    data[host.hostname][(key % ( cluster.name, service.type.lower(), role.type.lower()))] = self.CM_HEALTH_MAPPING[str(role.healthSummary)]
                    key = "hadoop.cm.role[%s,%s,%s,maintenanceMode]"
                    data[host.hostname][(key % ( cluster.name, service.type.lower(), role.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(role.maintenanceMode)]
                    key = "hadoop.cm.role[%s,%s,%s,roleState]"
                    data[host.hostname][(key % ( cluster.name, service.type.lower(), role.type.lower()))] = self.CM_SERVICE_MAPPING[str(role.roleState)]

                    for check in role.healthChecks:
                        key = "hadoop.cm.role.check[%s,%s,%s,%s,checkSummary]"
                        data[host.hostname][(key % (
                            cluster.name, service.type.lower(),
                            role.type.lower(),
                            check['name'].lower())
                        )] = self.CM_HEALTH_MAPPING[check['summary']]

        mgmt_service = self.cdh_api.get_cloudera_manager().get_service()
        key = "hadoop.cm.service[%s,%s,serviceState]"
        data[mgmt_hostname][(key % ( cluster.name, mgmt_service.type.lower()))] = self.CM_SERVICE_MAPPING[mgmt_service.serviceState]
        key = "hadoop.cm.service[%s,%s,healthSummary]"
        data[mgmt_hostname][(key % ( cluster.name, mgmt_service.type.lower()))] = self.CM_HEALTH_MAPPING[mgmt_service.healthSummary]
        key = "hadoop.cm.service[%s,%s,configStale]"
        data[mgmt_hostname][(key % ( cluster.name, mgmt_service.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(mgmt_service.configStale)]
        key = "hadoop.cm.service[%s,%s,maintenanceMode]"
        data[mgmt_hostname][(key % ( cluster.name, mgmt_service.type.lower()))] = self.CM_BOOLEAN_MAPPING[str(mgmt_service.maintenanceMode)]

        for check in mgmt_service.healthChecks:
            key = "hadoop.cm.service.check[%s,%s,%s,checkSummary]"
            data[mgmt_hostname][(key % ( cluster.name, mgmt_service.type.lower(), check['name'].lower()))] = self.CM_HEALTH_MAPPING[check['summary']]

        data[mgmt_hostname]['hadoop.cm.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = ClouderaHadoop().run()
    print((ret))
    sys.exit(ret)