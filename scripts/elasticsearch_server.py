#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Elasticsearch.
'''
import optparse
import socket
import sys
import simplejson
import protobix
from elasticsearch import Elasticsearch

class ElasticSearchServer(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

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

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs Elasticsearch call but do not send "
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
                                   "Discovery on Elasticsearch. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

        general_options = optparse.OptionGroup(parser, "Elasticsearch Configuration")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="Elasticsearch server hostname")
        general_options.add_option("-p", "--port", help="Elasticsearch server port",
                                   default=9200)
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

        return parser.parse_args()

    def _get_discovery(self, elasticsearch, hostname):
        discovery_data = {}

        discovery_data[hostname] = { "elasticsearch.cluster.discovery":[] }
        # Cluster wide metrics
        zbx_data = elasticsearch.cluster.health(request_timeout=1)
        cluster_list = {"{#ESCLUSTERNAME}": ("%s" % zbx_data['cluster_name']) }
        discovery_data[hostname]["elasticsearch.cluster.discovery"].append(cluster_list)

        return discovery_data

    def _get_metrics(self, elasticsearch, hostname):
        data = {}
        data[hostname] = {}
        
        # Cluster wide metrics
        cluster_data = elasticsearch.cluster.health(request_timeout=1)
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

        cluster_data = elasticsearch.cluster.stats()['indices']
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

        indice_data = elasticsearch.indices.stats()['_all']['total']
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
        return data

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
        #try:
        es = Elasticsearch(["%s:%s" % (hostname, self.options.port)],timeout=5,default_indices=[''])
        if self.options.mode == "update_items":
            zbx_container.set_type("items")
            data = self._get_metrics(es, hostname)
        elif self.options.mode == "discovery":
            zbx_container.set_type("lld")
            data = self._get_discovery(es, hostname)
        #except:
        #    return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
            zbx_container.add_item(hostname, "elasticsearch.zbx_version", self.__version__)
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
    ret = ElasticSearchServer().run()
    print ret
    sys.exit(ret)