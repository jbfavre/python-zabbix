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
import optparse
import socket
import urllib2
import simplejson
import protobix
import sys

class CouchbaseServer(protobix.SampleProbe):

    __version__="0.0.9"
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
            self.passman.add_password(
                None,
                "http://%s:%d/" % (hostname, int(port)),
                login, password
            )
            self.hostname = hostname
            self.port = port
            self.opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(self.passman))
            urllib2.install_opener(self.opener)

        def _do_call(self,uri):
            try:
                request = urllib2.Request( ("http://%s:%d%s" % (self.hostname, int(self.port), uri)))
                rawjson = self.opener.open(request, None, 10)
                if (rawjson):
                    return simplejson.load(rawjson)
            except urllib2.URLError as e:
                print self.CBS_CONN_ERR % e.reason

    ''' Pool class '''
    class Pool(object):

        def __init__(self,server):
            self.server = server
            self.pools_list = self._get_discovery()
            self.bucket = CouchbaseServer.Bucket(self.server, self.pools_list)

        def _get_status(self):
            pool_list=[]
            for pool in self.pools_list:
                pool_infos = self.server._do_call("/pools/%s/" % pool)
                pool_list.append(pool_infos)
            return pool_list

        def _get_discovery(self):
            pools = self.server._do_call('/pools/')
            pools_list=[]
            for pool in pools['pools']:
                pools_list.append(pool['name'])
            return pools_list

        def _get_metrics(self, hostname):
            data = {}
            data.update(self.bucket._get_metrics(hostname))
            pools = self._get_status()
            for pool in pools:
                for node in pool['nodes']:
                    nodename = node['hostname'].split(".")[0]
                    nodename = node['hostname'].split(":")[0]
                    ''' Limit items lookup to current node '''
                    if nodename != hostname:
                        continue
                    if not nodename in data:
                        data[nodename] = {}
                    zbx_key = 'couchbase.cluster.members'
                    data[nodename][zbx_key] = len(pool['nodes'])
                    if pool['rebalanceStatus'] in CouchbaseServer.CBS_RECOVERY_MAPPING.keys():
                        data[nodename]['couchbase.cluster.rebalanceStatus'] = \
                            CouchbaseServer.CBS_RECOVERY_MAPPING[pool['rebalanceStatus']]
                    for key in [ 'rebalance_success',
                                 'rebalance_start',
                                 'failover_node' ]:
                        zbx_key = 'couchbase.cluster.counters[{0}]'
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = pool['counters'][key]
                    for key in [ 'ram', 'hdd' ]:
                        zbx_key = 'couchbase.cluster.storageTotals[{0},{1}]'
                        zbx_key_fin = zbx_key.format(key, 'used')
                        value = pool['storageTotals'][key]['used']
                        data[nodename][zbx_key_fin] = value
                        zbx_key_fin = zbx_key.format(key, 'usedByData')
                        value = pool['storageTotals'][key]['usedByData']
                        data[nodename][zbx_key_fin] = value

                    zbx_key = "couchbase.node.status"
                    if node['status'] and \
                       node['status'] in CouchbaseServer.CBS_STATUS_MAPPING.keys():
                        data[nodename][zbx_key] = CouchbaseServer.CBS_STATUS_MAPPING[node['status']]
                    else:
                        data[nodename][zbx_key] = 3
                    zbx_key = "couchbase.node.recoveryType"
                    if node['recoveryType'] and \
                       node['recoveryType'] in CouchbaseServer.CBS_RECOVERY_MAPPING.keys():
                        data[nodename][zbx_key] = CouchbaseServer.CBS_RECOVERY_MAPPING[node['recoveryType']]
                    else:
                        data[nodename][zbx_key] = 3
                    zbx_key = "couchbase.node.clusterMembership"
                    if node['clusterMembership'] and \
                       node['clusterMembership'] in CouchbaseServer.CBS_MEMBERSHIP_MAPPING.keys():
                        data[nodename][zbx_key] = CouchbaseServer.CBS_MEMBERSHIP_MAPPING[node['clusterMembership']]
                    else:
                        data[nodename][zbx_key] = 3
                    for key in [ 'cpu_utilization_rate',
                                 'swap_used',
                                 'mem_free']:
                        zbx_key = "couchbase.node[systemStats,{0}]"
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = node['systemStats'][key]
                    for key in [ 'cmd_get',
                                 'couch_docs_actual_disk_size',
                                 'couch_docs_data_size',
                                 'couch_views_actual_disk_size',
                                 'couch_views_data_size',
                                 'curr_items',
                                 'curr_items_tot',
                                 'ep_bg_fetched',
                                 'mem_used',
                                 'get_hits',
                                 'ops',
                                 'vb_replica_curr_items' ]:
                        zbx_key = "couchbase.node.interestingStats[{0}]"
                        zbx_key = zbx_key.format(key)
                        data[nodename][zbx_key] = int(node['interestingStats'][key])
            return data

    ''' Bucket class '''
    class Bucket(object):
        def __init__(self,server, pool_list):
            self.server = server
            self.pool_list = pool_list
            self.buckets_list = self._get_discovery()

        def _get_status(self):
            bucket_list = {}
            for bucket_item in self.buckets_list:
                pool = bucket_item['pool']
                if not pool in bucket_list:
                    bucket_list[pool] = []
                bucket = bucket_item['bucket']
                bucket_uri = "/pools/{0}/buckets/{1}/"
                bucket_uri = bucket_uri.format(pool, bucket)
                bucket_infos = self.server._do_call(bucket_uri)
                bucket_list[pool].append(bucket_infos)
            return bucket_list

        def _get_discovery(self):
            for pool in self.pool_list:
                buckets_info = self.server._do_call('/pools/%s/buckets/' % pool)
                buckets_list=[]
                for bucket in buckets_info:
                    buckets_list.append({'pool': pool, 'bucket': bucket['name']})
            return buckets_list

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
                        for key in [ 'diskUsed',
                                     'memUsed',
                                     'diskFetches',
                                     'quotaPercentUsed',
                                     'opsPerSec',
                                     'dataUsed',
                                     'itemCount' ]:
                            zbx_key_fin = zbx_key.format(pool, bucket_infos['name'], key)
                            data[nodename][zbx_key_fin] = bucket_infos['basicStats'][key]
                    bucket_stats_uri = "/pools/{0}/buckets/{1}/stats/"
                    bucket_stats_uri = bucket_stats_uri.format(pool, bucket_infos['name'])
                    bucket_stats = self.server._do_call(bucket_stats_uri)
                    sample_list = [ 'curr_connections',
                                    'ops',
                                    'cmd_get',
                                    'cmd_set',
                                    'ep_cache_miss_rate',
                                    'couch_docs_fragmentation',
                                    'ep_queue_size',
                                    'ep_tmp_oom_errors',
                                    'ep_tap_total_qlen' ]
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

    def _init_probe(self):
        self.cnx = self.API(
            self.options.username,
            self.options.password,
            self.options.host,
            self.options.port)
        if self.options.host == 'localhost':
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host
        self.pools = self.Pool(self.cnx)
        ''' Initialize variables '''
        self.pool_key = "couchbase.pool"
        self.cluster_key = "couchbase.cluster"
        self.node_key = "couchbase.node"
        self.bucket_key = "couchbase.bucket"

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( CouchbaseServer, self)._parse_args()

        # Couchbase options
        couchbase_options = optparse.OptionGroup(parser, "Couchabse cluster "
                                                       "configuration options")
        couchbase_options.add_option("-H", "--host", default="localhost",
                                     help="Couchabse hostname")
        couchbase_options.add_option("-P", "--port", default=8091,
                                     help="Couchabse port. Default is 8091")
        couchbase_options.add_option('--username', default='zabbix',
                                     help='Couchbase admin username')
        couchbase_options.add_option('--password', default='zabbix',
                                     help='Couchbase admin password')

        parser.add_option_group(couchbase_options)
        (options, args) = parser.parse_args()
        return (options, args)

    def _get_metrics(self, hostname):
        data = {}
        ''' Get pools information. Currently only one pool exists,
            but Couchbase might add multiple pools supports later '''
        data.update(self.pools._get_metrics(self.hostname))
        data[hostname]['couchbase.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = CouchbaseServer().run()
    print((ret))
    sys.exit(ret)