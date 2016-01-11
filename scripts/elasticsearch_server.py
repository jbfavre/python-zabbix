#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Elasticsearch.
'''
import optparse
import socket
import sys
import simplejson
import protobix
from elasticsearch import Elasticsearch

class ElasticsearchServer(protobix.SampleProbe):
    __version__="0.0.9"

    ES_CLUSTER_BOOL_MAPPING ={
      False: 0,
      True: 1
    }
    ES_CLUSTER_STATUS_MAPPING={
      'green': 0,
      'yellow': 1,
      'red': 2
    }
    ES_INDICES_KEYS = {
        'suggest': [
            'current',
            'time_in_millis',
            'total'
        ],
        'search': [
            'fetch_current',
            'fetch_time_in_millis',
            'fetch_total',
            'query_current',
            'query_time_in_millis',
            'query_total',
            'open_contexts'
        ],
        'fielddata': [
            'evictions',
            'memory_size_in_bytes'
        ],
        'get': [
            'current',
            'exists_time_in_millis',
            'exists_total',
            'missing_time_in_millis',
            'missing_total',
            'time_in_millis',
            'total'
        ],
        'translog': [
            'operations',
            'size_in_bytes'
        ],
        'docs': [
            'count',
            'deleted'
        ],
        'segments': [
            'count',
            'fixed_bit_set_memory_in_bytes',
            'index_writer_max_memory_in_bytes',
            'index_writer_memory_in_bytes',
            'memory_in_bytes',
            'version_map_memory_in_bytes'
        ],
        'flush': [
            'total',
            'total_time_in_millis'
        ],
        'indexing': [
            'delete_current',
            'delete_time_in_millis',
            'delete_total',
            'index_current',
            'index_time_in_millis',
            'index_total',
            'is_throttled',
            'noop_update_total',
            'throttle_time_in_millis'
        ],
        'refresh': [
            'total_time_in_millis',
            'total'
        ],
        'query_cache': [
            'evictions',
            'hit_count',
            'memory_size_in_bytes',
            'miss_count'
        ],
        'warmer': [
            'current',
            'total',
            'total_time_in_millis'
        ],
        'filter_cache': [
            'evictions',
            'memory_size_in_bytes'
        ],
        'percolate': [
            'current',
            'memory_size',
            'memory_size_in_bytes',
            'queries',
            'time_in_millis',
            'total'
        ],
        'merges': [
            'current',
            'current_docs',
            'current_size_in_bytes',
            'total',
            'total_docs',
            'total_size_in_bytes',
            'total_time_in_millis'
        ],
        'store': [
            'size_in_bytes',
            'throttle_time_in_millis'
        ],
        'recovery': [
            'current_as_source',
            'current_as_target',
            'throttle_time_in_millis'
        ]
    }
    ES_JVM_KEYS = {
        'mem': [
            'heap_used_in_bytes',
            'heap_used_percent',
            'heap_committed_in_bytes',
            'heap_max_in_bytes',
            'non_heap_used_in_bytes',
            'non_heap_committed_in_bytes'
        ],
        'threads': [
            'count',
            'peak_count'
        ]
    }
    ES_THREAD_POOLS_KEYS = {
        "percolate": [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'fetch_shard_started': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'listener': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'index': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'refresh': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'suggest': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'generic': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'warmer': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'search': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'flush': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'optimize': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'fetch_shard_store': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'management': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'get': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'merge': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'bulk': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ],
        'snapshot': [
           'threads',
           'queue',
           'active',
           'rejected',
           'largest',
           'completed'
        ]
    }
    returnval = None

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host
        self.es = Elasticsearch(
            ["%s:%s" % (self.hostname, self.options.port)],
            timeout=25,
            default_indices=['']
        )
        self.discovery_key = 'elasticsearch.cluster.discovery'

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( ElasticsearchServer, self)._parse_args()

        # Elasticsearch options
        es_options = optparse.OptionGroup(parser, "Elasticsearch Configuration")
        es_options.add_option("-H", "--host", default="localhost",
                              help="Elasticsearch server hostname")
        es_options.add_option("-P", "--port", default=9200,
                              help="Elasticsearch server port")
        parser.add_option_group(es_options)
        (options, args) = parser.parse_args()
        return (options, args)

    def _get_discovery(self):
        data = { self.discovery_key:[] }
        # Cluster wide metrics
        zbx_data = self.es.cluster.health(request_timeout=1)
        cluster_list = {"{#ESCLUSTERNAME}": ("%s" % zbx_data['cluster_name']) }
        data[self.discovery_key].append(cluster_list)
        return { self.hostname: data }

    def _get_cluster_metrics(self):
        data = {}
        cluster_data = self.es.cluster.health(request_timeout=1, local=True)
        cluster_name = cluster_data['cluster_name']
        for key in cluster_data:
          if key != 'cluster_name':
            zbx_key = 'elasticsearch.cluster[{0},{1}]'
            zbx_key = zbx_key.format(cluster_name,key)
            if key == 'status':
              data[zbx_key] = self.ES_CLUSTER_STATUS_MAPPING[cluster_data[key]]
            elif cluster_data[key] in self.ES_CLUSTER_BOOL_MAPPING:
              data[zbx_key] = self.ES_CLUSTER_BOOL_MAPPING[cluster_data[key]]
            else:
              data[zbx_key] = cluster_data[key]

        # Check wether current node is master for the cluster
        whois_master = self.es.cat.master(local=True).split(" ")
        self.is_master = True if whois_master[3] == self.hostname else False
        zbx_key = 'elasticsearch.cluster[{0},is_master]'
        zbx_key = zbx_key.format(cluster_name)
        data[zbx_key] = self.ES_CLUSTER_BOOL_MAPPING[self.is_master]
        return data, cluster_name

    def _get_nodes_stats(self, cluster_name):
        data = {}
        nodes_stats = self.es.nodes.stats()
        for node in nodes_stats['nodes']:
            # Skip non data nodes
            if 'data' in nodes_stats['nodes'][node]['attributes'] and \
               nodes_stats['nodes'][node]['attributes']['data'] == 'false':
                continue
            hostname = nodes_stats['nodes'][node]['name']
            data[hostname] = {}
            # Get indices stats
            indices_stats = nodes_stats['nodes'][node]['indices']
            data[hostname].update(self._get_indices_stats(indices_stats))
            # Get jvm stats
            jvm_stats = nodes_stats['nodes'][node]['jvm']
            data[hostname].update(self._get_jvm_stats(jvm_stats))
            thread_pool_stats = nodes_stats['nodes'][node]['thread_pool']
            data[hostname].update(self._get_thread_pools_stats(thread_pool_stats))
        return data

    def _get_indices_stats(self, raw_data):
        data = {}
        zbx_key = 'elasticsearch.indices[{0},{1}]'
        for key in self.ES_INDICES_KEYS:
            for metric in self.ES_INDICES_KEYS[key]:
                real_key = zbx_key.format(key, metric)
                data[real_key] = raw_data[key][metric]
        return data

    def _get_jvm_stats(self, raw_data):
        data = {}
        zbx_key = 'elasticsearch.jvm[{0},{1}]'
        for key in self.ES_JVM_KEYS:
            for metric in self.ES_JVM_KEYS[key]:
                real_key = zbx_key.format(key, metric)
                data[real_key] = raw_data[key][metric]
        return data

    def _get_thread_pools_stats(self, raw_data):
        data = {}
        zbx_key = 'elasticsearch.thread_pools[{0},{1}]'
        for key in self.ES_THREAD_POOLS_KEYS:
            for metric in self.ES_THREAD_POOLS_KEYS[key]:
                real_key = zbx_key.format(key, metric)
                data[real_key] = raw_data[key][metric]
        return data

    def _get_metrics(self):
        # Get health status
        data = { self.hostname: {} }
        data[self.hostname], cluster_name = self._get_cluster_metrics()
        if data[self.hostname]['elasticsearch.cluster['+cluster_name+',is_master]'] == 1:
            nodes_data = self._get_nodes_stats(cluster_name)
            for host in nodes_data:
                if host in data:
                    data[host].update(nodes_data[host])
                else:
                    data[host] = nodes_data[host]
        data[self.hostname]['elasticsearch.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = ElasticsearchServer().run()
    print((ret))
    sys.exit(ret)
