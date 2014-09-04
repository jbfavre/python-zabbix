#!/usr/bin/env python
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
import platform
import protobix

__version__ = '0.0.2'
ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

class RabbitMQAPI(object):

    def __init__(self, user_name='guest', password='guest',
                 host_name='', port=15672, conf='rabbitmq.yaml'):
        self.user_name = user_name
        self.password = password
        self.host_name = host_name or socket.gethostname()
        self.port = port
        self.discovery_key = "rabbitmq.queues.discovery"

        ''' Load config file '''
        with open(conf, 'r') as f:
          config = yaml.load(f)
        self.queue_limits = config['queues_limits']

        ''' Prepare regex pattern for queue exclusion '''
        pattern_string = '|'.join(config['exclude_pattern'])
        self.exclude_patterns = re.compile(pattern_string)

    def call_api(self, path):
        # Call the REST API and convert the results into JSON.
        url = 'http://{0}:{1}/api/{2}'.format(self.host_name, self.port, path)
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, url, self.user_name, self.password)
        handler = urllib2.HTTPBasicAuthHandler(password_mgr)
        return json.loads(urllib2.build_opener(handler).open(url).read())

    def get_discovery(self):
        data = {self.discovery_key:[]}
        for queue in self.call_api('queues'):
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

    def get_metrics(self):
        data = {}
        queues_list = self.call_api('queues')
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
            dl_queue = self.call_api(api_path)
            data[zbx_key] = dl_queue.get('messages', 0)

            ''' Get queue's master node here so that we can trigger Zabbix
                alert based on ${HOSTNAME} Zabbix macro match '''
            zbx_key = "rabbitmq.queue[{0},{1},master]"
            zbx_key = zbx_key.format(queue['vhost'], queue['name'])
            value=0
            if queue.get('node', 0).split('@')[1] == self.host_name:
                value=1
            data[zbx_key] = value

            ''' Get message_stats rates '''
            message_stats = queue.get('message_stats', {})

            for item in ['deliver_get', 'ack', 'get', 'publish', 'redeliver']:
                rate_key = message_stats.get('%s_details'%item, {})
                zbx_key = "rabbitmq.queue[{0},{1},rate,{2}]"
                zbx_key = zbx_key.format(queue['vhost'], queue['name'], item)
                data[zbx_key] = rate_key.get('rate', 0)

        data["rabbitmq.zbx_version"] = __version__

        return data

    '''def check_server(self, item, node_name):
        # First, check the overview specific items
        if item == 'message_stats_deliver_get':
	    return self.call_api('overview').get('message_stats', {}).get('deliver_get',0)
        elif item == 'message_stats_publish':
	    return self.call_api('overview').get('message_stats', {}).get('publish',0)
        elif item == 'rabbitmq_version':
	    return self.call_api('overview').get('rabbitmq_version', 'None')
        # Return the value for a specific item in a node's details.
        node_name = node_name.split('.')[0]
        for nodeData in self.call_api('nodes'):
            if node_name in nodeData['name']:
                return nodeData.get(item)
        return 'Not Found'
    '''

def parse_args():
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

    (options, args) = parser.parse_args()

    return (options, args)

def main():

    (options, args) = parse_args()
    if options.host == 'localhost':
        hostname = platform.node()
    else:
        hostname = options.host

    try:
        rmq = RabbitMQAPI(user_name=options.username,
                          password=options.password,
                          host_name=hostname,
                          port=options.port)
    except:
        return 1

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = rmq.get_metrics()

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = rmq.get_discovery()

    zbx_container.add(data)
    zbx_container.set_host(options.zabbix_server)
    zbx_container.set_port(int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)
    zbx_container.set_dryrun(options.dry)

    try:
        zbx_response = zbx_container.send(zbx_container)

    except protobix.SenderException as zbx_exception:
        if options.debug:
            print ZBX_CONN_ERR % zbx_exception.err_text
        return 2

    else:
        return 0

if __name__ == '__main__':
    ret = main()
    print ret
