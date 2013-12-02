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
import platform
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

__version__="0.0.2"

CM_API_VERSION = 5
CM_COMMISSION_MAPPING = { "UNKNOWN": -1,
                          "COMMISSIONED": 0,
                          "DECOMMISSIONING": 1,
                          "DECOMMISSIONED": 2 }
CM_HEALTH_MAPPING = { "HISTORY_NOT_AVAILABLE": -1,
                    "NOT_AVAILABLE": -1,
                    "DISABLED": -1,
                    "GOOD": 0,
                    "CONCERNING": 1,
                    "BAD": 2 }
CM_SERVICE_MAPPING = { "HISTORY_NOT_AVAILABLE": -1,
                       "UNKNOWN": -1,
                       "STARTING": 0,
                       "STARTED": 0,
                       "STOPPING": 1,
                       "STOPPED": 1,
                       "NA": 0 }
CM_BOOLEAN_MAPPING = { "False": 0,
                       "True": 1 }

ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
    ''' Parse the script arguments
    '''
    parser = optparse.OptionParser()

    parser.add_option("-d", "--dry-run", action="store_true",
                          help="Performs CDH API calls but do not send "
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
                               "Discovery on Hadoop Cloudera Manager API. "
                               "Default is to get & send items")
    parser.add_option_group(mode_group)
    parser.set_defaults(mode="update_items")

    general_options = optparse.OptionGroup(parser, "Hadoop Cloudera Manager API Configuration")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="Hadoop Cloudera Manager API hostname")
    general_options.add_option("-p", "--port", help="CM API port", default=None)
    general_options.add_option("-P", "--passfile", metavar="FILE",
                               help="File containing Hadoop Cloudera Manager API username "
                                    "and password, colon-delimited on a single line.  E.g. "
                                    "\"user:pass\"")
    general_options.add_option("--use-tls", action="store_true",
                               help="If specified, force TLS use. Default is NO", default=False)
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

    ''' Parse the 'passfile' - it must contain the username and password,
        colon-delimited on a single line. E.g.:
        $ cat ~/protected/cm_pass
        admin:admin
    '''
    required = ["host", "passfile"]

    if options.mode == "update_items":
        required.append("zabbix_server")

    for required_opt in required:
        if getattr(options, required_opt) is None:
            parser.error("Please specify the required argument: --%s" %
                         (required_opt.replace('_','-'),))

    return (options, args)

def get_discovery(cdh_api, mgmt_hostname):
    discovery_data = {}

    for cluster in cdh_api.get_all_clusters():

        for instance in cluster.list_hosts():
            host = cdh_api.get_host(instance.hostId)
            discovery_data[host.hostname] = { "hadoop.cm.cluster.discovery":[],
                                              "hadoop.cm.cluster.check.discovery":[],
                                              "hadoop.cm.host.discovery":[],
                                              "hadoop.cm.host.check.discovery":[],
                                              "hadoop.cm.role.discovery":[],
                                              "hadoop.cm.role.check.discovery":[],
                                              "hadoop.cm.service.discovery":[],
                                              "hadoop.cm.service.check.discovery":[] }

            host_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name) }
            discovery_data[host.hostname]["hadoop.cm.host.discovery"].append(host_list)

            for check in host.healthChecks:
                check_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                              "{#HDPHOSTCHECKNAME}": ("%s" % check['name'].lower()) }
                discovery_data[host.hostname]["hadoop.cm.host.check.discovery"].append(check_list)

        for service in cluster.get_all_services(view="full"):
            service_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                            "{#HDPSERVICENAME}": ("%s" % service.type.lower()) }
            discovery_data[mgmt_hostname]["hadoop.cm.service.discovery"].append(service_list)

            for check in service.healthChecks:
                check_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                              "{#HDPSERVICENAME}": ("%s" % service.type.lower()),
                              "{#HDPSERVICECHECKNAME}": ("%s" % check['name'].lower()) }
                discovery_data[mgmt_hostname]["hadoop.cm.service.check.discovery"].append(check_list)

            for role in service.get_all_roles(view="full"):
                role_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                             "{#HDPSERVICENAME}": ("%s" % service.type.lower()),
                             "{#HDPROLENAME}": ("%s" % role.type.lower()) }
                discovery_data[role.hostRef.hostId]["hadoop.cm.role.discovery"].append(role_list)

                for check in role.healthChecks:
                    check_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                                  "{#HDPSERVICENAME}": ("%s" % service.type.lower()),
                                  "{#HDPROLENAME}": ("%s" % role.type.lower()),
                                  "{#HDPROLECHECKNAME}": ("%s" % check['name'].lower()) }
                    discovery_data[role.hostRef.hostId]["hadoop.cm.role.check.discovery"].append(check_list)

        cluster_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name) }
        discovery_data[mgmt_hostname]["hadoop.cm.cluster.discovery"].append(cluster_list)

    mgmt_service = cdh_api.get_cloudera_manager().get_service()
    service_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                    "{#HDPSERVICENAME}": ("%s" % mgmt_service.type.lower()) }
    discovery_data[mgmt_hostname]["hadoop.cm.service.discovery"].append(service_list)

    for check in mgmt_service.healthChecks:
        check_list = {"{#HDPCLUSTERNAME}": ("%s" % cluster.name),
                      "{#HDPSERVICENAME}": ("%s" % mgmt_service.type.lower()),
                      "{#HDPSERVICECHECKNAME}": ("%s" % check['name'].lower()) }
        discovery_data[mgmt_hostname]["hadoop.cm.service.check.discovery"].append(check_list)

    return discovery_data

def get_metrics(cdh_api, mgmt_hostname):
    data = {}

    for cluster in cdh_api.get_all_clusters():
        if not mgmt_hostname in data:
            data[mgmt_hostname] = {}

        data[mgmt_hostname][("hadoop.cm.cluster[%s,version]" % cluster.name)] =  cluster.version
        data[mgmt_hostname][("hadoop.cm.cluster[%s,maintenanceMode]" % cluster.name)] = CM_BOOLEAN_MAPPING[str(cluster.maintenanceMode)]
        for instance in cluster.list_hosts():
            host = cdh_api.get_host(instance.hostId)
            if not host.hostname in data:
                data[host.hostname] = {}

            data[host.hostname][("hadoop.cm.host[%s,maintenanceMode]" % cluster.name)] = CM_BOOLEAN_MAPPING[str(host.maintenanceMode)]
            data[host.hostname][("hadoop.cm.host[%s,healthSummary]" % cluster.name)] = CM_HEALTH_MAPPING[str(host.healthSummary)]
            data[host.hostname][("hadoop.cm.host[%s,commissionState]" % cluster.name)] = CM_COMMISSION_MAPPING[str(host.commissionState)]
            difference = datetime.now() - host.lastHeartbeat
            differenceTotalSeconds = (difference.microseconds + (difference.seconds + difference.days*24*3600) * 1e6) / 1e6
            data[host.hostname][("hadoop.cm.host[%s,lastHeartbeat]" % cluster.name)] = differenceTotalSeconds
            ''' Only works with Python 2.7
               differenceTotalSeconds = (datetime.now() - host.lastHeartbeat).total_seconds()
               data[host.hostname][("hadoop.cm.host[%s,lastHeartbeat]" % cluster.name)] = differenceTotalSeconds'''
            for check in host.healthChecks:
                data[host.hostname][("hadoop.cm.host.check[%s,%s]" % (cluster.name, check['name'].lower()))] = CM_HEALTH_MAPPING[check['summary']]

        for service in cluster.get_all_services(view="full"):
            data[mgmt_hostname][("hadoop.cm.service[%s,%s,serviceState]" % ( cluster.name, service.type.lower()))] = CM_SERVICE_MAPPING[service.serviceState]
            data[mgmt_hostname][("hadoop.cm.service[%s,%s,healthSummary]" % ( cluster.name, service.type.lower()))] = CM_HEALTH_MAPPING[service.healthSummary]
            data[mgmt_hostname][("hadoop.cm.service[%s,%s,configStale]" % ( cluster.name, service.type.lower()))] = CM_BOOLEAN_MAPPING[str(service.configStale)]
            data[mgmt_hostname][("hadoop.cm.service[%s,%s,maintenanceMode]" % ( cluster.name, service.type.lower()))] = CM_BOOLEAN_MAPPING[str(service.maintenanceMode)]

            for check in service.healthChecks:
                data[mgmt_hostname][("hadoop.cm.service.check[%s,%s,%s,checkSummary]" % ( cluster.name, service.type.lower(), check['name'].lower()))] = CM_HEALTH_MAPPING[check['summary']]

            for role in service.get_all_roles(view="full"):
                data[role.hostRef.hostId][("hadoop.cm.role[%s,%s,%s,commissionState]" % ( cluster.name, service.type.lower(), role.type.lower()))] = CM_COMMISSION_MAPPING[str(role.commissionState)]
                data[role.hostRef.hostId][("hadoop.cm.role[%s,%s,%s,configStale]" % ( cluster.name, service.type.lower(), role.type.lower()))] = CM_BOOLEAN_MAPPING[str(role.configStale)]
                data[role.hostRef.hostId][("hadoop.cm.role[%s,%s,%s,healthSummary]" % ( cluster.name, service.type.lower(), role.type.lower()))] = CM_HEALTH_MAPPING[str(role.healthSummary)]
                data[role.hostRef.hostId][("hadoop.cm.role[%s,%s,%s,maintenanceMode]" % ( cluster.name, service.type.lower(), role.type.lower()))] = CM_BOOLEAN_MAPPING[str(role.maintenanceMode)]
                data[role.hostRef.hostId][("hadoop.cm.role[%s,%s,%s,roleState]" % ( cluster.name, service.type.lower(), role.type.lower()))] = CM_SERVICE_MAPPING[str(role.roleState)]

                for check in role.healthChecks:
                    data[role.hostRef.hostId][("hadoop.cm.role.check[%s,%s,%s,%s,checkSummary]" % ( cluster.name, service.type.lower(), role.type.lower(), check['name'].lower()))] = CM_HEALTH_MAPPING[check['summary']]

    mgmt_service = cdh_api.get_cloudera_manager().get_service()
    data[mgmt_hostname][("hadoop.cm.service[%s,%s,serviceState]" % ( cluster.name, mgmt_service.type.lower()))] = CM_SERVICE_MAPPING[mgmt_service.serviceState]
    data[mgmt_hostname][("hadoop.cm.service[%s,%s,healthSummary]" % ( cluster.name, mgmt_service.type.lower()))] = CM_HEALTH_MAPPING[mgmt_service.healthSummary]
    data[mgmt_hostname][("hadoop.cm.service[%s,%s,configStale]" % ( cluster.name, mgmt_service.type.lower()))] = CM_BOOLEAN_MAPPING[str(mgmt_service.configStale)]
    data[mgmt_hostname][("hadoop.cm.service[%s,%s,maintenanceMode]" % ( cluster.name, mgmt_service.type.lower()))] = CM_BOOLEAN_MAPPING[str(mgmt_service.maintenanceMode)]

    for check in mgmt_service.healthChecks:
        data[mgmt_hostname][("hadoop.cm.service.check[%s,%s,%s,checkSummary]" % ( cluster.name, mgmt_service.type.lower(), check['name'].lower()))] = CM_HEALTH_MAPPING[check['summary']]

    return data

def main():
    (options, args) = parse_args()

    try:
        (options.username, options.password) = open(options.passfile, 'r').readline().rstrip('\n').split(':')
    except:
        print >> sys.stderr, "Unable to read username and password from file '%s'. "
        "Make sure the file is readable and contains a single line of "
        "the form \"<username>:<password>\"" % options.passfile

    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    cdh_api = get_root_resource(options.host, options.port, options.username,
                                options.password, options.use_tls, CM_API_VERSION)

    zbx_container = protobix.DataContainer()
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data = get_metrics(cdh_api, hostname)
    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data = get_discovery(cdh_api, hostname)

    zbx_container.add(data)
    zbx_container.add_item(hostname, "hadoop.cm.zbx_version", __version__)

    zbx_container.set_host(options.zabbix_server)
    zbx_container.set_port(int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)

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
