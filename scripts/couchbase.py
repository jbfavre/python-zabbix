#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Couchabse server monitoring from Zabbix.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
    - Performs an HTTP request on http://couchabse_server/, parse json output,
        add items and send them to Zabbix server.
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.
'''
import optparse
import socket
import urllib2
import simplejson
import sys

import protobix

class CouchbaseServer(object):

    __version__ = '0.0.8'

    CBS_MEMBERSHIP_MAPPING = { 'active': 0,
                               'inactiveAdded': 1,
                               'inactiveFailed': 2 }
    CBS_STATUS_MAPPING = { 'healthy': 0,
                           'unhealthy': 1 }
    CBS_RECOVERY_MAPPING = { 'none': 0 }
    CBS_CONN_ERR = "ERR - unable to get data from Couchabse [%s]"

    ''' Low level class to actually perform API calls '''
    class API(object):
        def __init__(self, login, password, hostname, port=8091):
            self.passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            self.passman.add_password(None, "http://%s:%d/" % (hostname, int(port)), login, password)
            self.hostname = hostname
            self.port = port
            self.opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(self.passman))
            urllib2.install_opener(self.opener)

        def _doCall(self,uri):
            try:
                request = urllib2.Request( ("http://%s:%d%s" % (self.hostname, int(self.port), uri)))
                rawjson = self.opener.open(request, None, 10)
                if (rawjson):
                    return simplejson.load(rawjson)
            except urllib2.URLError as e:
                print CBS_CONN_ERR % e.reason

    ''' Pool class '''
    class Pool(object):
        def __init__(self,server):
            self.server = server
            self.pools_list = self._get_list()
            self.bucket = CouchbaseServer.Bucket(self.server, self.pools_list)

        def _get_list(self):
            pools = self.server._doCall('/pools/')
            pools_list=[]
            for pool in pools['pools']:
                pools_list.append(pool['name'])
            return pools_list

        def _get_status(self):
            pool_list=[]
            for pool in self.pools_list:
                pool_infos = self.server._doCall("/pools/%s/" % pool)
                pool_list.append(pool_infos)
            return pool_list

        def _get_metrics(self, hostname):
            data = {}
            data.update(self.bucket._get_metrics(hostname))
            pools = self._get_status()
            for pool in pools:
                for node in pool['nodes']:
                    nodename = node['hostname'].split(".")[0]
                    ''' Limit items lookup to current node '''
                    if nodename != hostname:
                        continue
                    if not nodename in data:
                        data[nodename] = {}
                    data[nodename]["couchbase.cluster.members"] = len(pool['nodes'])
                    if pool['rebalanceStatus'] in self.CBS_RECOVERY_MAPPING.keys():
                        data[nodename]["couchbase.cluster.rebalanceStatus"] = \
                            self.CBS_RECOVERY_MAPPING[pool['rebalanceStatus']]
                    for key in ['rebalance_success', 'rebalance_start', 'failover_node']:
                        zbx_key = 'couchbase.cluster.counters[{0}]'
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = pool['counters'][key]
                    for key in [ 'ram', 'hdd' ]:
                        zbx_key = 'couchbase.cluster.storageTotals[{0},{1}]'
                        zbx_key_fin = zbx_key.format(key, 'used')
                        data[nodename][zbx_key_fin] = pool['storageTotals'][key]['used']
                        zbx_key_fin = zbx_key.format(key, 'usedByData')
                        data[nodename][zbx_key_fin] = pool['storageTotals'][key]['usedByData']

                    zbx_key = "couchbase.node.status"
                    if node['status'] and node['status'] in self.CBS_STATUS_MAPPING.keys():
                        data[nodename][zbx_key] = self.CBS_STATUS_MAPPING[node['status']]
                    else:
                        data[nodename][zbx_key] = 3
                    zbx_key = "couchbase.node.recoveryType"
                    if node['recoveryType'] and node['recoveryType'] in self.CBS_RECOVERY_MAPPING.keys():
                        data[nodename][zbx_key] = self.CBS_RECOVERY_MAPPING[node['recoveryType']]
                    else:
                        data[nodename][zbx_key] = 3
                    zbx_key = "couchbase.node.clusterMembership"
                    if node['clusterMembership'] and node['clusterMembership'] in self.CBS_MEMBERSHIP_MAPPING.keys():
                        data[nodename][zbx_key] = self.CBS_MEMBERSHIP_MAPPING[node['clusterMembership']]
                    else:
                        data[nodename][zbx_key] = 3
                    for key in ['cpu_utilization_rate', 'swap_used', 'mem_free']:
                        zbx_key = "couchbase.node[systemStats,{0}]"
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = node['systemStats'][key]
                    for key in ['cmd_get', 'couch_docs_actual_disk_size', 'couch_docs_data_size',
                                'couch_views_actual_disk_size', 'couch_views_data_size',
                                'curr_items', 'curr_items_tot', 'ep_bg_fetched', 'mem_used',
                                'get_hits', 'ops', 'vb_replica_curr_items' ]:
                        zbx_key = "couchbase.node.interestingStats[{0}]"
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = int(node['interestingStats'][key])
            return data

    ''' Bucket class '''
    class Bucket(object):
        def __init__(self,server, pool_list):
            self.server = server
            self.pool_list = pool_list
            self.buckets_list = self._get_list()

        def _get_list(self):
            for pool in self.pool_list:
                buckets_info = self.server._doCall('/pools/%s/buckets/' % pool)
                buckets_list=[]
                for bucket in buckets_info:
                    buckets_list.append({'pool': pool, 'bucket': bucket['name']})
            return buckets_list

        def _get_status(self):
            bucket_list = {}
            for bucket_item in self.buckets_list:
                pool = bucket_item['pool']
                if not pool in bucket_list:
                    bucket_list[pool] = []
                bucket = bucket_item['bucket']
                bucket_uri = "/pools/{0}/buckets/{1}/"
                bucket_uri = bucket_uri.format(pool, bucket)
                bucket_infos = self.server._doCall(bucket_uri)
                bucket_list[pool].append(bucket_infos)
            return bucket_list

        def _get_metrics(self, hostname):
            data = {}
            bucket_list = self._get_status()
            for pool in bucket_list:
                for bucket_infos in bucket_list[pool]:
                    for node in bucket_infos['vBucketServerMap']['serverList']:
                        nodename = node.split(":")[0]
                        ''' Limit items lookup to current node '''
                        if nodename != hostname:
                            continue
                        data[nodename] = {}
                        zbx_key = "couchbase.bucket.basicStats[{0},{1},{2}]"
                        for key in ['diskUsed', 'memUsed', 'diskFetches',
                                    'quotaPercentUsed', 'opsPerSec',
                                    'dataUsed', 'itemCount']:
                            zbx_key_fin = zbx_key.format(pool, bucket_infos['name'], key)
                            data[nodename][zbx_key_fin] = bucket_infos['basicStats'][key]
                    bucket_stats_uri = "/pools/{0}/buckets/{1}/stats/"
                    bucket_stats_uri = bucket_stats_uri.format(pool, bucket_infos['name'])
                    bucket_stats = self.server._doCall(bucket_stats_uri)
                    sample_list = [ 'curr_connections', 'ops', 'cmd_get',
                                    'cmd_set', 'ep_cache_miss_rate',
                                    'couch_docs_fragmentation', 'ep_queue_size',
                                    'ep_tmp_oom_errors', 'ep_tap_total_qlen' ]
                    zbx_key = "couchbase.bucket.advancedStats[{0},{1},{2}]"
                    for key in sample_list:
                        nodename = node.split(":")[0]
                        ''' Limit items lookup to current node '''
                        if nodename != hostname:
                            continue
                        sample = bucket_stats['op']['samples'][key]
                        zbx_key_fin = zbx_key.format(pool, bucket_infos['name'], key)
                        data[nodename][zbx_key_fin] = int(sum(sample)/len(sample))
            return data

    def _get_metrics(self):
        data = {}
        ''' Get pools information. Currently only one pool exists,
            but Couchbase might add multiple pools supports later '''
        data.update(self.pools._get_metrics(self.hostname))
        return data

    def _get_discovery(self):
        self.pools = self.pools._get_list()
        for pool in self.pools:
            print pool

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs MySQL calls but do not send "
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
                                   "Discovery on MySQL. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

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
            self.cnx = CouchbaseServer.API(
                self.options.username,
                self.options.password,
                hostname,
                self.options.port
            )
            self.hostname = hostname
            self.pools = self.Pool(self.cnx)
            ''' Initialize variables '''
            self.pool_key = "couchbase.pool"
            self.cluster_key = "couchbase.cluster"
            self.node_key = "couchbase.node"
            self.bucket_key = "couchbase.bucket"
            data = {}
            zbx_container.set_type("items")
            data = self._get_metrics()
        except:
            return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
            zbx_container.add_item(hostname, "couchbase.zbx_version", self.__version__)
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
    ret = CouchbaseServer().run()
    print ret
    sys.exit(ret)