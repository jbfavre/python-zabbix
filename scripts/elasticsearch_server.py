#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Elasticsearch.
'''
import optparse
import socket
import sys
import simplejson
import protobix
#from elasticsearch import Elasticsearch
import requests

class ElasticsearchServer(protobix.SampleProbe):
    __version__="0.0.9"

    ES_CLUSTER_MAPPING={
      'green': 0,
      'yellow': 1,
      'red': 2,
      False: 0,
      True: 1
    }
    ES_CLUSTER_HEALTH_10 = [
        'active_primary_shards',
        'active_shards',
        'initializing_shards',
        'number_of_data_nodes',
        'number_of_nodes',
        'relocating_shards',
        'status',
        'timed_out',
        'unassigned_shards'
    ]
    ES_CLUSTER_HEALTH_16 = [
        'number_of_in_flight_fetch',
        'number_of_pending_tasks'
    ]
    ES_CLUSTER_HEALTH_17 = [
        'delayed_unassigned_shards'
    ]
    ES_NODES_STATS_10 = [
        'indices.docs.count',
        'indices.docs.deleted',
        'indices.fielddata.evictions',
        'indices.fielddata.memory_size_in_bytes',
        'indices.filter_cache.evictions',
        'indices.filter_cache.memory_size_in_bytes',
        'indices.flush.total',
        'indices.flush.total_time_in_millis',
        'indices.get.current',
        'indices.get.exists_time_in_millis',
        'indices.get.exists_total',
        'indices.get.missing_time_in_millis',
        'indices.get.missing_total',
        'indices.get.time_in_millis',
        'indices.get.total',
        'indices.indexing.delete_current',
        'indices.indexing.delete_time_in_millis',
        'indices.indexing.delete_total',
        'indices.indexing.index_current',
        'indices.indexing.index_time_in_millis',
        'indices.indexing.index_total',
        'indices.merges.current',
        'indices.merges.current_docs',
        'indices.merges.current_size_in_bytes',
        'indices.merges.total',
        'indices.merges.total_docs',
        'indices.merges.total_size_in_bytes',
        'indices.merges.total_time_in_millis',
        'indices.percolate.current',
        'indices.percolate.memory_size',
        'indices.percolate.memory_size_in_bytes',
        'indices.percolate.queries',
        'indices.percolate.time_in_millis',
        'indices.percolate.total',
        'indices.refresh.total',
        'indices.refresh.total_time_in_millis',
        'indices.search.fetch_current',
        'indices.search.fetch_time_in_millis',
        'indices.search.fetch_total',
        'indices.search.open_contexts',
        'indices.search.query_current',
        'indices.search.query_time_in_millis',
        'indices.search.query_total',
        'indices.segments.count',
        'indices.segments.memory_in_bytes',
        'indices.store.size_in_bytes',
        'indices.store.throttle_time_in_millis',
        'indices.translog.operations',
        'indices.translog.size_in_bytes',
        'indices.warmer.current',
        'indices.warmer.total',
        'indices.warmer.total_time_in_millis',
        'jvm.mem.heap_used_in_bytes',
        'jvm.mem.heap_used_percent',
        'jvm.mem.heap_committed_in_bytes',
        'jvm.mem.heap_max_in_bytes',
        'jvm.mem.non_heap_used_in_bytes',
        'jvm.mem.non_heap_committed_in_bytes',
        'jvm.mem.pools.young.used_in_bytes',
        'jvm.mem.pools.young.max_in_bytes',
        'jvm.mem.pools.young.peak_used_in_bytes',
        'jvm.mem.pools.young.peak_max_in_bytes',
        'jvm.mem.pools.survivor.used_in_bytes',
        'jvm.mem.pools.survivor.max_in_bytes',
        'jvm.mem.pools.survivor.peak_used_in_bytes',
        'jvm.mem.pools.survivor.peak_max_in_bytes',
        'jvm.mem.pools.old.used_in_bytes',
        'jvm.mem.pools.old.max_in_bytes',
        'jvm.mem.pools.old.peak_used_in_bytes',
        'jvm.mem.pools.old.peak_max_in_bytes',
        'jvm.threads.count',
        'jvm.threads.peak_count',
        'jvm.gc.collectors.young.collection_count',
        'jvm.gc.collectors.young.collection_time_in_millis',
        'jvm.gc.collectors.old.collection_count',
        'jvm.gc.collectors.old.collection_time_in_millis',
        'jvm.buffer_pools.direct.count',
        'jvm.buffer_pools.direct.used_in_bytes',
        'jvm.buffer_pools.direct.total_capacity_in_bytes',
        'jvm.buffer_pools.mapped.count',
        'jvm.buffer_pools.mapped.used_in_bytes',
        'jvm.buffer_pools.mapped.total_capacity_in_bytes',
        'thread_pool.bulk.active',
        'thread_pool.bulk.completed',
        'thread_pool.bulk.largest',
        'thread_pool.bulk.queue',
        'thread_pool.bulk.rejected',
        'thread_pool.bulk.threads',
        'thread_pool.flush.active',
        'thread_pool.flush.completed',
        'thread_pool.flush.largest',
        'thread_pool.flush.queue',
        'thread_pool.flush.rejected',
        'thread_pool.flush.threads',
        'thread_pool.generic.active',
        'thread_pool.generic.completed',
        'thread_pool.generic.largest',
        'thread_pool.generic.queue',
        'thread_pool.generic.rejected',
        'thread_pool.generic.threads',
        'thread_pool.get.active',
        'thread_pool.get.completed',
        'thread_pool.get.largest',
        'thread_pool.get.queue',
        'thread_pool.get.rejected',
        'thread_pool.get.threads',
        'thread_pool.index.active',
        'thread_pool.index.completed',
        'thread_pool.index.largest',
        'thread_pool.index.queue',
        'thread_pool.index.rejected',
        'thread_pool.index.threads',
        'thread_pool.management.active',
        'thread_pool.management.completed',
        'thread_pool.management.largest',
        'thread_pool.management.queue',
        'thread_pool.management.rejected',
        'thread_pool.management.threads',
        'thread_pool.merge.active',
        'thread_pool.merge.completed',
        'thread_pool.merge.largest',
        'thread_pool.merge.queue',
        'thread_pool.merge.rejected',
        'thread_pool.merge.threads',
        'thread_pool.optimize.active',
        'thread_pool.optimize.completed',
        'thread_pool.optimize.largest',
        'thread_pool.optimize.queue',
        'thread_pool.optimize.rejected',
        'thread_pool.optimize.threads',
        'thread_pool.percolate.active',
        'thread_pool.percolate.completed',
        'thread_pool.percolate.largest',
        'thread_pool.percolate.queue',
        'thread_pool.percolate.rejected',
        'thread_pool.percolate.threads',
        'thread_pool.refresh.active',
        'thread_pool.refresh.completed',
        'thread_pool.refresh.largest',
        'thread_pool.refresh.queue',
        'thread_pool.refresh.rejected',
        'thread_pool.refresh.threads',
        'thread_pool.search.active',
        'thread_pool.search.completed',
        'thread_pool.search.largest',
        'thread_pool.search.queue',
        'thread_pool.search.rejected',
        'thread_pool.search.threads',
        'thread_pool.snapshot.active',
        'thread_pool.snapshot.completed',
        'thread_pool.snapshot.largest',
        'thread_pool.snapshot.queue',
        'thread_pool.snapshot.rejected',
        'thread_pool.snapshot.threads',
        'thread_pool.suggest.active',
        'thread_pool.suggest.completed',
        'thread_pool.suggest.queue',
        'thread_pool.suggest.rejected',
        'thread_pool.suggest.threads',
        'thread_pool.warmer.active',
        'thread_pool.warmer.completed',
        'thread_pool.warmer.largest',
        'thread_pool.warmer.queue',
        'thread_pool.warmer.rejected',
        'thread_pool.warmer.threads'
    ]
    ES_NODES_STATS_13 = [
        'indices.segments.index_writer_memory_in_bytes',
        'indices.segments.version_map_memory_in_bytes',
        'indices.suggest.current',
        'indices.suggest.time_in_millis',
        'indices.suggest.total'
    ]
    ES_NODES_STATS_17 = [
        'indices.indexing.is_throttled',
        'indices.indexing.noop_update_total',
        'indices.indexing.throttle_time_in_millis',
        'indices.query_cache.evictions',
        'indices.query_cache.hit_count',
        'indices.query_cache.memory_size_in_bytes',
        'indices.query_cache.miss_count',
        'indices.recovery.current_as_source',
        'indices.recovery.current_as_target',
        'indices.recovery.throttle_time_in_millis',
        'indices.segments.fixed_bit_set_memory_in_bytes',
        'indices.segments.index_writer_max_memory_in_bytes',
        'thread_pool.fetch_shard_started.active',
        'thread_pool.fetch_shard_started.completed',
        'thread_pool.fetch_shard_started.largest',
        'thread_pool.fetch_shard_started.queue',
        'thread_pool.fetch_shard_started.rejected',
        'thread_pool.fetch_shard_started.threads',
        'thread_pool.fetch_shard_store.active',
        'thread_pool.fetch_shard_store.completed',
        'thread_pool.fetch_shard_store.largest',
        'thread_pool.fetch_shard_store.queue',
        'thread_pool.fetch_shard_store.rejected',
        'thread_pool.fetch_shard_store.threads',
        'thread_pool.listener.active',
        'thread_pool.listener.completed',
        'thread_pool.listener.largest',
        'thread_pool.listener.queue',
        'thread_pool.listener.rejected',
        'thread_pool.listener.threads',
        'thread_pool.suggest.largest',
    ]

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host
        self._get_es_version('/')
        # Build metrics list
        self.cluster_metrics = self.ES_CLUSTER_HEALTH_10
        self.nodes_stats_metrics = self.ES_NODES_STATS_10
        if self.es_version >= [1,3,0]:
            self.nodes_stats_metrics.extend(self.ES_NODES_STATS_13)
        if self.es_version >= [1, 6, 0]:
            self.cluster_metrics.extend(self.ES_CLUSTER_HEALTH_16)
        if self.es_version >= [1, 7, 0]:
            self.cluster_metrics.extend(self.ES_CLUSTER_HEALTH_17)
            self.nodes_stats_metrics.extend(self.ES_NODES_STATS_17)
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

    def _do_get_rawdata(self,url):
        try:
            resp = requests.get(
                'http://' + self.hostname + ':' + str(self.options.port) + url,
                timeout=1
            )
            resp.raise_for_status()
        except Exception as e:
            self.logger.error('Step 2 - failed to open: ' + url)
            raise
        return resp

    def _process_path(self,zbx_key, path, value):
        data = {}
        for key in path.split('.'):
            if value is not None:
                value = value.get(key,None)
            else:
                break
        if value is not None:
            real_key = zbx_key.format(path)
            if value in self.ES_CLUSTER_MAPPING:
                value = self.ES_CLUSTER_MAPPING[value]
            data[real_key] = value
        else:
            self.logger.warning('Could not find key ' + path)
        return data

    def _get_es_version(self, url):
        raw_data = self._do_get_rawdata(url)
        try:
            raw_data = raw_data.json()
        except TypeError:
            raw_data = raw_data.json
        self.es_version = map(int, raw_data['version']['number'].split('.')[0:3])

    def _cluster_health(self, url):
        data = {}
        zbx_key = 'elasticsearch.cluster.health.{0}'
        raw_data = self._do_get_rawdata(url)
        try:
            raw_data = raw_data.json()
        except TypeError:
            raw_data = raw_data.json
        self.cluster_name = raw_data['cluster_name']
        # Process metrics list
        for path in self.cluster_metrics:
            data.update(
                self._process_path(zbx_key, path, raw_data)
            )
        return data

    def _cluster_pending_tasks(self,url):
        zbx_key = 'elasticsearch.cluster.pending_tasks.{0}'
        raw_data = self._do_get_rawdata(url)
        try:
            raw_data = raw_data.json()
        except TypeError:
            raw_data = raw_data.json
        # Process tasks list
        pending_tasks = {
            'urgent': 0,
            'high': 0
        }
        for task in raw_data.get('tasks', []):
            if task:
                pending_tasks[task.get('priority')] += 1
        data = {
            'elasticsearch.cluster.pending_tasks.total': sum(pending_tasks.values()),
            'elasticsearch.cluster.pending_tasks.urgent': pending_tasks['urgent'],
            'elasticsearch.cluster.pending_tasks.high': pending_tasks['high']
        }
        return data

    def _nodes_stats(self, url):
        data = {}
        zbx_key = 'elasticsearch.{0}'
        nodes_stats = self._do_get_rawdata(url)
        try:
            nodes_stats = nodes_stats.json()
        except TypeError:
            nodes_stats = nodes_stats.json
        # Process metrics list
        for node in nodes_stats['nodes']:
            # Skip non data nodes
            if 'attributes' in nodes_stats['nodes'][node] and \
               'data' in nodes_stats['nodes'][node]['attributes'] and \
               nodes_stats['nodes'][node]['attributes']['data'] == 'false':
                continue
            raw_data = nodes_stats['nodes'][node]
            data = {}
            for path in self.nodes_stats_metrics:
                data.update(
                    self._process_path(zbx_key, path, raw_data)
                )
        return data

    def _master_status(self, url):
        data = {}
        # Check wether current node is master for the cluster
        whois_master = self._do_get_rawdata(url)
        whois_master = whois_master.text.split(' ')
        self.is_cluster_master = True if whois_master[3] == self.hostname else False
        zbx_key = 'elasticsearch.cluster.is_master'
        data[zbx_key] = self.ES_CLUSTER_MAPPING[self.is_cluster_master]
        return data

    def _get_discovery(self):
        data = { self.discovery_key:[] }
        # Cluster wide metrics
        cluster_health = self._cluster_health('/_cluster/health/')
        cluster_list = {"{#ESCLUSTERNAME}": ("%s" % self.cluster_name) }
        cluster_version = {"{#ESCLUSTERVERSION}": ("%s" % self.es_version) }
        data[self.discovery_key].append(cluster_list)
        data[self.discovery_key].append(cluster_version)
        return { self.hostname: data }

    def _get_metrics(self):
        data = { self.hostname: {} }

        # Get cluster health status
        data[self.hostname] = self._cluster_health('/_cluster/health/')
        data[self.hostname].update(
            self._master_status('/_cat/master/')
        )

        # Get local node stats
        nodes_data = self._nodes_stats('/_nodes/_local/stats/')
        data[self.hostname].update(nodes_data)

        data[self.hostname]['elasticsearch.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = ElasticsearchServer().run()
    print((ret))
    sys.exit(ret)
