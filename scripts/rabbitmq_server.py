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

class RabbitMQServer(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = "ERR - unable to send data to Zabbix [%s]"

    def _call_api(self, path):
        # Call the REST API and convert the results into JSON.
        url = 'http://{0}:{1}/api/{2}'.format(self.options.host, self.options.port, path)
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, url, self.options.username, self.options.password)
        handler = urllib2.HTTPBasicAuthHandler(password_mgr)
        return json.loads(urllib2.build_opener(handler).open(url).read())

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

        return data

    def _get_metrics(self):
        data = {}
        connections_stats = self._call_api('connections')
        zbx_key = 'rabbitmq.connections'
        data[zbx_key] = len(connections_stats)
        global_stats = self._call_api('overview')
        overview_items = {
            'message_stats': [
                'ack', 'confirm', 'deliver', 'deliver_get',
                'get', 'get_no_ack', 'publish', 'redeliver'
            ],
            'queue_totals' : [
                'messages', 'messages_ready', 'messages_unacknowledged'
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
                dl_queue = self.call_api(api_path)
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

        data["rabbitmq.zbx_version"] = self.__version__

        return data

    def _parse_args(self):
        ''' Parse the script arguments'''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs RabbitMQ API calls but do not send "
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
                                   "Discovery on RabbitMQ API. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

        general_options = optparse.OptionGroup(parser, "RabbitMQ API Configuration")
        general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                                   help="RabbitMQ API hostname")
        general_options.add_option("-p", "--port", help="RabbitMQ API port", default=15672)
        general_options.add_option('--username', help='RabbitMQ API username',
                          default='nagios')
        general_options.add_option('--password', help='RabbitMQ API password',
                          default='nagios')
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

    def _init_container(self):
        zbx_container = protobix.DataContainer(
            data_type = 'items',
            zbx_host  = self.options.zabbix_server,
            zbx_port  = int(self.options.zabbix_port),
            debug     = self.options.debug,
            dryrun    = self.options.dry
        )
        return zbx_container

    def run(self, config_file='/etc/zabbix/rabbitmq_server.yaml'):
        (self.options, args) = self._parse_args()
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        hostname = self.options.host

        # Step 1: init container
        try:
            zbx_container = self._init_container()
        except:
            return 1

        # Step 2: get data
        #try:
        ''' Load config file '''
        with open(config_file, 'r') as f:
          config = yaml.load(f)
        self.queue_limits = config['queues_limits']
        ''' Prepare regex pattern for queue exclusion '''
        pattern_string = '|'.join(config['exclude_pattern'])
        self.exclude_patterns = re.compile(pattern_string)

        data = {}
        if self.options.mode == "update_items":
            zbx_container.set_type("items")
            data[hostname] = self._get_metrics()

        elif self.options.mode == "discovery":
            zbx_container.set_type("lld")
            data[hostname] = self._get_discovery()
        #except:
        #    return 2

        # Step 3: format & load data into container
        try:
            zbx_container.add(data)
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
    ret = RabbitMQServer().run()
    print ret
    sys.exit(ret)