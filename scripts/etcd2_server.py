#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Apache TrafficServer monitoring from Zabbix.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
    - Performs an HTTP request on http://ats_server/_stats, parse json output,
        add items and send them to Zabbix server.
    - You can blacklist some items adding them to ITEM_BL list.
    - it also send its version which should match with template version. If not,
        Zabbix will raise a trigger.


    $ curl -s http://127.0.0.1:2379/v2/stats/self | jq .
    {
      "name": "coreos1",
      "id": "6064d54512894a8e",
      "state": "StateFollower",
      "startTime": "2015-11-24T08:19:21.806102985Z",
      "leaderInfo": {
        "leader": "72bc9008c24500cc",
        "uptime": "2m14.185480285s",
        "startTime": "2015-11-24T08:19:24.108571536Z"
      },
      "recvAppendRequestCnt": 1254,
      "recvPkgRate": 8.694416588068645,
      "recvBandwidthRate": 855.2262876853722,
      "sendAppendRequestCnt": 0
    }

    $ curl -s http://127.0.0.1:2379/v2/stats/leader | jq .
    {
      "leader": "72bc9008c24500cc",
      "followers": {
        "6064d54512894a8e": {
          "latency": {
            "current": 0.001297,
            "average": 0.0029719713044827163,
            "standardDeviation": 0.028773967146203967,
            "minimum": 0.000597,
            "maximum": 3.71652
          },
          "counts": {
            "fail": 0,
            "success": 25788
          }
        },
        "eb19ee38296bfc05": {
          "latency": {
            "current": 0.001141,
            "average": 0.01072091116919599,
            "standardDeviation": 1.2924880937018346,
            "minimum": 0.000572,
            "maximum": 206.927497
          },
          "counts": {
            "fail": 33,
            "success": 25633
          }
        }
      }
    }

    $ curl -s http://127.0.0.1:2379/v2/stats/store | jq .
    {
      "getsSuccess": 139427,
      "getsFail": 173970,
      "setsSuccess": 11031,
      "setsFail": 0,
      "deleteSuccess": 101,
      "deleteFail": 23,
      "updateSuccess": 3222,
      "updateFail": 10,
      "createSuccess": 78,
      "createFail": 25,
      "compareAndSwapSuccess": 8070,
      "compareAndSwapFail": 2,
      "compareAndDeleteSuccess": 8,
      "compareAndDeleteFail": 1,
      "expireCount": 4,
      "watchers": 0
    }
'''
import sys,os
import optparse
import socket
import urllib2
import simplejson
import protobix

class Etcd2Server(protobix.SampleProbe):

    __version__ = '0.0.9'
    cluster_topology = {}

    def _get_url(self, url):
        json = None
        rawdata = urllib2.build_opener().open(
            "http://%s:%s%s" % (
                self.options.host,
                self.options.port,
                url
            ),
            None, # data
            1 # timeout
        )
        if (rawdata):
            json = simplejson.load(rawdata)
        return json

    def _get_cluster_topology(self):
        json = self._get_url('/v2/members')
        if (json):
            for host in json['members']:
                self.cluster_topology[host['id']] = host

    def _get_health(self):
        json = self._get_url('/health')
        data = {}
        if 'health' in json and json['health'] == 'true':
            data['etcd2.is_healthy'] = 1
        else:
            data['etcd2.is_healthy'] = 0
        return data

    def _get_self_stats(self):
        stats = self._get_url('/v2/stats/self')
        current_id = stats['id']
        leader_id = stats['leaderInfo']['leader']
        data = {}
        ''' Set default values to 0 to avoid multiple templates management depending on state '''
        if current_id == leader_id:
            ''' Leader has only sendPkgRate & sendBandwidthRate '''
            data['etcd2.recvPkgRate'] = 0
            data['etcd2.recvBandwidthRate'] = 0
            data['etcd2.is_master'] = 1
            data['etcd2.sendPkgRate'] = stats['sendPkgRate']
            data['etcd2.sendBandwidthRate'] = stats['sendBandwidthRate']
        else:
            ''' Followers have only recvPkgRate & recvBandwidthRate '''
            data['etcd2.sendPkgRate'] = 0
            data['etcd2.sendBandwidthRate'] = 0
            data['etcd2.is_master'] = 0
            data['etcd2.recvPkgRate'] = stats['recvPkgRate']
            data['etcd2.recvBandwidthRate'] = stats['recvBandwidthRate']
        return data

    def _get_store_stats(self):
        stats = self._get_url('/v2/stats/store')
        data = {}
        for item in stats:
            data["etcd2.%s" % item] = stats[item]
        return data

    def _get_leader_stats(self):
        stats = self._get_url('/v2/stats/leader')
        data = { self.hostname: {} }
        for host in stats['followers']:
            real_hostname = self.cluster_topology[host]['name']
            if real_hostname not in data:
                data[real_hostname] = {}
            for item in stats['followers'][host]:
                for metric in stats['followers'][host][item]:
                    data[real_hostname]["etcd2.%s[%s]" % (item, metric)] = stats['followers'][host][item][metric]
                    data[self.hostname]["etcd2.%s[%s]" % (item, metric)] = 0
        return data
        

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( Etcd2Server, self)._parse_args()

        # TrafficServer options
        etcd2_options = optparse.OptionGroup(
            parser,
            'CoreOS Etcd2 cluster configuration options'
        )
        etcd2_options.add_option(
            '-H', '--host', default='localhost',
            help='Coreos Etcd2 hostname'
        )
        etcd2_options.add_option(
            '-P', '--port', default=2379,
            help='Coreos Etcd2 port. Default is 2379'
        )
        parser.add_option_group(etcd2_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host

    def _get_metrics(self):
        data = { self.hostname: {} }
        ''' Check node state '''
        data[self.hostname].update(self._get_health())
        ''' Check node stats '''
        data[self.hostname].update(self._get_self_stats())
        ''' Check store stats '''
        data[self.hostname].update(self._get_store_stats())
        ''' If leader, let's get followers's latency infos '''
        self._get_cluster_topology()
        if data[self.hostname]['etcd2.is_master'] == 1:
            leader_data = self._get_leader_stats()
            for host in leader_data:
                if host not in data:
                    data[host] = {}
                data[host].update(leader_data[host])
        data[self.hostname]['etcd2.zbx_version'] = self.__version__
        return data

if __name__ == '__main__':
    ret = Etcd2Server   ().run()
    print ret
    sys.exit(ret)
