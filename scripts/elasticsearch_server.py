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
    searchkeys = [
      'query_total',
      'fetch_time_in_millis',
      'fetch_total',
      'fetch_time',
      'query_current',
      'fetch_current',
      'query_time_in_millis'
    ]
    getkeys = [
      'missing_total',
      'exists_total',
      'current',
      'time_in_millis',
      'missing_time_in_millis',
      'exists_time_in_millis',
      'total'
    ]
    docskeys = [
      'count',
      'deleted'
    ]
    indexingkeys = [
      'delete_time_in_millis',
      'index_total',
      'index_current',
      'delete_total',
      'index_time_in_millis',
      'delete_current'
    ]
    storekeys = [
      'size_in_bytes',
      'throttle_time_in_millis'
    ]
    cachekeys = [
      'filter_size_in_bytes',
      'field_size_in_bytes',
      'field_evictions'
    ]
    clusterkeys = searchkeys + getkeys + docskeys + indexingkeys + storekeys
    returnval = None

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host
        self.es = Elasticsearch(
            ["%s:%s" % (self.hostname, self.options.port)],
            timeout=25,
            default_indices=['']
        )

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

    def _get_discovery(self, hostname):
        discovery_data = {}

        discovery_data[hostname] = { "elasticsearch.cluster.discovery":[] }
        # Cluster wide metrics
        zbx_data = self.es.cluster.health(request_timeout=1)
        cluster_list = {"{#ESCLUSTERNAME}": ("%s" % zbx_data['cluster_name']) }
        discovery_data[hostname]["elasticsearch.cluster.discovery"].append(cluster_list)

        return discovery_data

    def _get_metrics(self, hostname):
        data = {}
        data[hostname] = {}
        
        # Cluster wide metrics
        cluster_data = self.es.cluster.health(request_timeout=1)
        cluster_name = cluster_data['cluster_name']
        for key in cluster_data:
          if key != 'cluster_name':
            zbx_key = 'elasticsearch.cluster[{0},{1}]'
            zbx_key = zbx_key.format(cluster_name,key)
            if key == 'status':
              data[hostname][zbx_key] = self.ES_CLUSTER_STATUS_MAPPING[cluster_data[key]]
            elif cluster_data[key] in self.ES_CLUSTER_BOOL_MAPPING:
              data[hostname][zbx_key] = self.ES_CLUSTER_BOOL_MAPPING[cluster_data[key]]
            else:
              data[hostname][zbx_key] = cluster_data[key]

        cluster_data = self.es.cluster.stats()['indices']
        zbx_key = 'elasticsearch.indices.{0}'
        for key in ['count', 'fielddata', 'filter_cache']:
          if key == 'count':
            real_key = zbx_key.format(key + '[' + cluster_name + ']',)
            data[hostname][real_key] = int(cluster_data[key])
          else:
            real_key = zbx_key.format(key + '[' + cluster_name + ',evictions]')
            data[hostname][real_key] = int(cluster_data[key]['evictions'])
            real_key = zbx_key.format(key + '[' + cluster_name + ',memory_size_in_bytes]')
            data[hostname][real_key] = int(cluster_data[key]['memory_size_in_bytes'])

        indice_data = self.es.indices.stats()['_all']['total']
        for key in ['search', 'indexing', 'docs', 'refresh', 'merges']:
          zbx_key = 'elasticsearch.indices.{0}'
          if key == 'count':
            real_key = zbx_key.format('docs')
            data[hostname][real_key] = int(indice_data[key]['count']) 
          elif key in ['refresh','merges']:
            real_key = zbx_key.format(key + '[' + cluster_name + ',total]')
            data[hostname][real_key] = int(indice_data[key]['total'])
            real_key = zbx_key.format(key + '[' + cluster_name + ',total_time_in_millis]')
            data[hostname][real_key] = int(indice_data[key]['total_time_in_millis'])
          elif key == 'search':
            real_key = zbx_key.format(key + '[' + cluster_name + ',query_total]')
            data[hostname][real_key] = int(indice_data[key]['query_total'])
            real_key = zbx_key.format(key + '[' + cluster_name + ',query_time_in_millis]')
            data[hostname][real_key] = int(indice_data[key]['query_time_in_millis'])
            real_key = zbx_key.format(key + '[' + cluster_name + ',query_current]')
            data[hostname][real_key] = int(indice_data[key]['query_current'])
          elif key == 'indexing':
            real_key = zbx_key.format(key + '[' + cluster_name + ',index_total]')
            data[hostname][real_key] = int(indice_data[key]['index_total'])
            real_key = zbx_key.format(key + '[' + cluster_name + ',index_time_in_millis]')
            data[hostname][real_key] = int(indice_data[key]['index_time_in_millis'])
          else:
            ''' Should never be there '''
        data[hostname]['elasticsearch.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = ElasticsearchServer().run()
    print((ret))
    sys.exit(ret)