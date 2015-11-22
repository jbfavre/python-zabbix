#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    Copyright (c) 2014 Jean Baptiste Favre.
    Sample script for Zabbix integration with RabbitMQ API.

Inspired by https://github.com/jasonmcintosh/rabbitmq-zabbix

RabbitMQ monitoring basics:
* http://rabbitmq.1065348.n5.nabble.com/Monitoring-A-Queue-td22581.html
* http://rabbitmq.1065348.n5.nabble.com/Management-API-and-monitoring-td30826.html
* http://www.rabbitmq.com/blog/2012/04/25/rabbitmq-performance-measurements-part-2/
'''

import optparse
import yaml
import re
import urllib2
import json
import socket
import sys
import protobix

class RabbitMQServer(protobix.SampleProbe):

    __version__ = '0.0.9'

    def _call_api(self, path):
        # Call the REST API and convert the results into JSON.
        url = 'http://{0}:{1}/api/{2}'.format(self.options.host, self.options.port, path)
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, url, self.options.username, self.options.password)
        handler = urllib2.HTTPBasicAuthHandler(password_mgr)
        return json.loads(urllib2.build_opener(handler).open(url).read())

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( RabbitMQServer, self)._parse_args()

        general_options = optparse.OptionGroup(parser, "RabbitMQ API Configuration")
        general_options.add_option("-H", "--host", default="localhost",
                                   help="RabbitMQ API hostname")
        general_options.add_option("-P", "--port", default=15672,
                                   help="RabbitMQ API port")
        general_options.add_option('--username', default='zabbix',
                                   help='RabbitMQ API username')
        general_options.add_option('--password', default='zabbix',
                                   help='RabbitMQ API password')
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host
        ''' Load config file '''
        with open(self.options.config, 'r') as f:
          config = yaml.load(f)
        self.queue_limits = config['queues_limits']
        ''' Prepare regex pattern for queue exclusion '''
        pattern_string = '|'.join(config['exclude_pattern'])
        self.exclude_patterns = re.compile(pattern_string)

    def _get_discovery(self):
        self.discovery_key = "rabbitmq.queues.discovery"
        data = {self.discovery_key:[]}
        for queue in self._call_api('queues'):
            ''' Skip queues matching exclude_patterns '''
            if self.exclude_patterns.match(queue['name']): continue
            try:
              msg_limit = self.queue_limits[queue['vhost']][queue['name']]['nb_msg']
            except:
              msg_limit = self.queue_limits['default']['nb_msg']
            try:
              rate_limit = self.queue_limits[queue['vhost']][queue['name']]['rate_ratio']
            except:
              rate_limit = self.queue_limits['default']['rate_ratio']
            element = { '{#RMQVHOSTNAME}': queue['vhost'],
                        '{#RMQQUEUENAME}': queue['name'],
                        '{#RMQMSGTHRESH}':  msg_limit,
                        '{#RMQRATIOTHRES}':  rate_limit }
            data[self.discovery_key].append(element)
        return { self.hostname: data }

    def _get_metrics(self):
        data = {}
        global_stats = self._call_api('overview')
        overview_items = {
            'message_stats': [
                'ack', 'confirm', 'deliver', 'deliver_get',
                'get', 'get_no_ack', 'publish', 'redeliver'
            ],
            'queue_totals' : [
                'messages', 'messages_ready', 'messages_unacknowledged'
            ],
            'object_totals' : [
                'channels', 'connections', 'consumers', 'exchanges', 'queues'
            ]
        }
        for item_family in overview_items:
            zbx_key = 'rabbitmq.{0}[{1}]'
            values_family = global_stats.get(item_family, 0)
            for item in overview_items[item_family]:
                real_key = zbx_key.format(item_family, item)
                data[real_key] = values_family.get(item, 0)
        queues_list = self._call_api('queues')
        for queue in queues_list:
            if self.exclude_patterns.match(queue['name']): continue
            ''' Get global messages count for considered queue '''
            zbx_key = "rabbitmq.queue[{0},{1},count,message]"
            zbx_key = zbx_key.format(queue['vhost'], queue['name'])
            data[zbx_key] = queue.get('messages', 0)
            ''' Get DL messages count for considered queue '''
            zbx_key = "rabbitmq.queue[{0},{1},count,dl_message]"
            zbx_key = zbx_key.format(queue['vhost'], queue['name'])
            api_path = 'queues/{0}/{1}_dl'.format(queue['vhost'], queue['name'])
            try:
                dl_queue = self._call_api(api_path)
                data[zbx_key] = dl_queue.get('messages', 0)
            except:
                data[zbx_key] = 0
            ''' Get queue's master node here so that we can trigger Zabbix
                alert based on ${HOSTNAME} Zabbix macro match '''
            zbx_key = "rabbitmq.queue[{0},{1},master]"
            zbx_key = zbx_key.format(queue['vhost'], queue['name'])
            value=0
            if (queue.get('node', 0).split('@')[1] == socket.gethostname()) or \
               (queue.get('node', 0).split('@')[1] == self.options.host):
                value=1
            data[zbx_key] = value
            ''' Get message_stats rates '''
            message_stats = queue.get('message_stats', {})
            for item in ['deliver_get', 'ack', 'get', 'publish', 'redeliver']:
                rate_key = message_stats.get('%s_details'%item, {})
                zbx_key = "rabbitmq.queue[{0},{1},rate,{2}]"
                zbx_key = zbx_key.format(queue['vhost'], queue['name'], item)
                data[zbx_key] = rate_key.get('rate', 0)
        data['rabbitmq.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = RabbitMQServer().run()
    print ret
    sys.exit(ret)
