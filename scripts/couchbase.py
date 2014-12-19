#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Couchabse server monitoring from Zabbix.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
    - Performs an HTTP request on http://couchabse_server/, parse json output,
        add items and send them to Zabbix server.
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.
'''
import sys
import optparse
import platform
import urllib2
import simplejson

import protobix

__version__="0.0.1"

ITEM_BL = [
    '',
    ''
]

CBS_MEMBERSHIP_MAPPING = { 'active': 0,
                           'inactiveAdded': 1,
                           'inactiveFailed': 2 }
CBS_STATUS_MAPPING = { 'healthy': 0 }
CBS_RECOVERY_MAPPING = { 'none': 0 }
CBS_CONN_ERR = "ERR - unable to get data from Couchabse [%s]"

ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

def parse_args():
    ''' Parse the script arguments
    '''
    parser = optparse.OptionParser(description="Get Couchabse statistics, "
                                    "format them and send the result to Zabbix")

    parser.add_option("-d", "--dry", action="store_true",
                               help="Performs Couchabse API calls but do not "
                                    "send anything to the Zabbix server. Can be "
                                    "used for both Update & Discovery mode")
    parser.add_option("-D", "--debug", action="store_true",
                               help="Enable debug mode. This will prevent bulk "
                                    "send operations and force sending items one "
                                    "after the other, displaying result for each "
                                    "one")
    parser.add_option("-v", "--verbose", action="store_true",
                               help="When used with debug option, will force value "
                                    "display for each items managed. Beware that it "
                                    "can be pretty much verbose, specialy for LLD")

    general_options = optparse.OptionGroup(parser, "Couchabse cluster "
                                                   "configuration options")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="Couchabse hostname")
    general_options.add_option("-p", "--port", default=8091,
                               help="Couchabse port"
                                    "Default is 8091")
    general_options.add_option('--username', help='Couchbase admin username',
                      default='zabbix')
    general_options.add_option('--password', help='Couchbase admin password',
                      default='zabbix')

    parser.add_option_group(general_options)

    zabbix_options = optparse.OptionGroup(parser, "Zabbix configuration")
    zabbix_options.add_option("--zabbix-server", metavar="HOST", default="localhost",
                               help="The hostname of Zabbix server or "
                                    "proxy, default is localhost.")
    zabbix_options.add_option("--zabbix-port", metavar="PORT", default=10051,
                               help="The port on which the Zabbix server or "
                                    "proxy is running, default is 10051.")
    parser.add_option_group(zabbix_options)

    (options, args) = parser.parse_args()

    return (options, args)

def main():
    (options, args) = parse_args()
    data = {}
    rawjson = ""
    zbxret = 0

    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    zbx_container = protobix.DataContainer("items", options.zabbix_server, int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)
    zbx_container.set_dryrun(options.dry)

    try:
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, "http://%s:%d/pools/nodes" % (options.host, int(options.port)), options.username, options.password)
        urllib2.install_opener(urllib2.build_opener(urllib2.HTTPBasicAuthHandler(passman)))
        request = urllib2.Request( ("http://%s:%d/pools/nodes" % (options.host, int(options.port))))
        opener  = urllib2.build_opener()
        rawjson = opener.open(request, None, 1)
    except urllib2.URLError as e:
        print e
        if options.debug:
            print CBS_CONN_ERR % e.reason
        return 1
    else:

        if (rawjson):
            json = simplejson.load(rawjson)
            for node in json['nodes']:
                hostname = node['hostname'].split(":")[0]
                if json['rebalanceStatus'] in CBS_RECOVERY_MAPPING.keys():
                    zbx_container.add_item( hostname, "couchbase.cluster.rebalanceStatus", CBS_RECOVERY_MAPPING[json['rebalanceStatus']])
                zbx_container.add_item( hostname, "couchbase.cluster.counters[rebalance_success]", json['counters']['rebalance_success'])
                zbx_container.add_item( hostname, "couchbase.cluster.counters[rebalance_start]", json['counters']['rebalance_start'])
                zbx_container.add_item( hostname, "couchbase.cluster.counters[failover_node]", json['counters']['failover_node'])
                zbx_container.add_item( hostname, "couchbase.cluster.storageTotals[ram,used]", json['storageTotals']['ram']['used'])
                zbx_container.add_item( hostname, "couchbase.cluster.storageTotals[ram,usedByData]", json['storageTotals']['ram']['usedByData'])
                zbx_container.add_item( hostname, "couchbase.cluster.storageTotals[hdd,used]", json['storageTotals']['hdd']['used'])
                zbx_container.add_item( hostname, "couchbase.cluster.storageTotals[hdd,usedByData]", json['storageTotals']['hdd']['usedByData'])

                if node['status'] and node['status'] in CBS_STATUS_MAPPING.keys():
                    zbx_container.add_item( hostname, "couchbase.node.status", CBS_STATUS_MAPPING[node['status']])
                if node['recoveryType'] and node['recoveryType'] in CBS_RECOVERY_MAPPING.keys():
                    zbx_container.add_item( hostname, "couchbase.node.recoveryType", CBS_RECOVERY_MAPPING[node['recoveryType']])
                if node['clusterMembership'] and node['clusterMembership'] in CBS_RECOVERY_MAPPING.keys():
                    zbx_container.add_item( hostname, "couchbase.node.clusterMembership", CBS_RECOVERY_MAPPING[node['clusterMembership']])
                zbx_container.add_item( hostname, "couchbase.node[systemStats,cpu_utilization_rate]", node['systemStats']['cpu_utilization_rate'])
                zbx_container.add_item( hostname, "couchbase.node[systemStats,swap_used]", node['systemStats']['swap_used'])
                zbx_container.add_item( hostname, "couchbase.node[systemStats,mem_free]", node['systemStats']['mem_free'])

                zbx_container.add_item( hostname, "couchbase.node[interestingStats,cmd_get]", node['interestingStats']['cmd_get'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,couch_docs_actual_disk_size]", node['interestingStats']['couch_docs_actual_disk_size'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,couch_docs_data_size]", node['interestingStats']['couch_docs_data_size'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,couch_views_actual_disk_size]", node['interestingStats']['couch_views_actual_disk_size'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,couch_views_data_size]", node['interestingStats']['couch_views_data_size'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,curr_items]", node['interestingStats']['curr_items'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,curr_items_tot]", node['interestingStats']['curr_items_tot'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,ep_bg_fetched]", node['interestingStats']['ep_bg_fetched'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,mem_used]", node['interestingStats']['mem_used'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,get_hits]", node['interestingStats']['get_hits'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,ops]", node['interestingStats']['ops'])
                zbx_container.add_item( hostname, "couchbase.node[interestingStats,vb_replica_curr_items]", node['interestingStats']['vb_replica_curr_items'])

        zbx_container.add_item(hostname, "couchbase.zbx_version", __version__)

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
    sys.exit(ret)
