#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
import sys
import optparse
import socket
import simplejson
import re

import protobix

import getopt
from telnetlib import Telnet

# ZooKeeper Commands: The Four Letter Words 
# Referer: http://zookeeper.apache.org/doc/r3.4.6/zookeeperAdmin.html#sc_zkCommands

CommandKey={
'conf':['clientPort','dataDir','dataLogDir','tickTime','maxClientCnxns','minSessionTimeout','maxSessionTimeout','serverId','initLimit','syncLimit','electionAlg','electionPort','quorumPort','peerType'],
'ruok':['state'],
'mntr':['zk_version','zk_avg_latency','zk_max_latency','zk_min_latency','zk_packets_received','zk_packets_sent','zk_num_alive_connections','zk_outstanding_requests','zk_server_state','zk_znode_count','zk_watch_count','zk_ephemerals_count','zk_approximate_data_size','zk_open_file_descriptor_count','zk_max_file_descriptor_count','zk_followers','zk_synced_followers','zk_pending_syncs']
}

class ZooKeeperServer(protobix.SampleProbe):
    __version__="0.0.9"

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = super( ZooKeeperServer, self)._parse_args()

        general_options = optparse.OptionGroup(parser, "ZooKeeper "
                                                       "configuration options")
        general_options.add_option("-H", "--host", metavar="HOST", default="127.0.0.1",
                                   help="Server FQDN")
        general_options.add_option("-C", "--zkCommand", metavar="COMMAND", default="mntr",
                                   help="ZooKeeper command")
        general_options.add_option("-P", "--port", default=2181,
                                   help="ZooKeeper port"
                                        "Default is 2181")
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)
    def _init_probe(self):
        if self.options.host == 'localhost' or self.options.host == '127.0.0.1' :
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host
    def _get_metrics(self):
        data = {}
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        s.connect( ( self.options.host, self.options.port ) )
        s.send( self.options.zkCommand )
        rawdata = ''
        output = s.recv(1024)
        while output:
            rawdata += output
            output = s.recv(1024)
        s.close
        if (rawdata):
            items = {}
            if self.options.zkCommand == 'mntr':
                for line in rawdata.splitlines() :
                    parts = line.split('\t')
                    index = parts[0]
                    items[index] = parts[1]
            elif self.options.zkCommand == 'conf':
                for line in rawdata.splitlines() :
                    parts = line.split('=')
                    index = parts[0]
                    items[index] = parts[1]
            elif self.options.zkCommand == 'ruok':
                if rawdata == 'imok':
                    items['state'] = 1
                else:
                    items['state'] = 0
            for item in items:
                data[("zookeeper.%s" % item)] = items[item]
            data['zookeeper.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = ZooKeeperServer().run()
    print ret
    sys.exit(ret)