#!/usr/bin/env python
''' Copyright (c) 2015 Clement Vasseur.
    Sample script for hekad monitoring from Zabbix.
    - Performs an HTTP request on heka dashboard, parse json output, diff with latest values
        add items and send them to Zabbix server.
    - Uses python-protobix module from https://github.com/jbfavre/python-zabbix
'''
import optparse
import socket
import urllib2
import simplejson
import protobix
import sys
import os.path

class HekadServer(protobix.SampleProbe):
    __version__="0.0.9"

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = super( HekadServer, self)._parse_args()

        general_options = optparse.OptionGroup(parser, "Hekad "
                                                       "configuration options")
        general_options.add_option("-H", "--host", metavar="HOST", default="127.0.0.1",
                                   help="Server FQDN")
        general_options.add_option("-P", "--port", default=4352,
                                   help="Hekad port. Default is 4352")
        parser.add_option_group(general_options)

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost' or self.options.host == '127.0.0.1' :
            self.hostname = socket.getfqdn()
        else:
            self.hostname = self.options.host
        self.port = self.options.port


    def _do_call(self,uri):
        try:
            request = urllib2.Request( ("http://%s:%d%s" % (self.hostname, int(self.port), uri)))
            rawjson = urllib2.urlopen(request, None, 10)
            if (rawjson):
                return simplejson.load(rawjson)
        except urllib2.URLError as e:
            print self.CBS_CONN_ERR % e.reason


    def _get_metrics(self):
        json = HekadServer._do_call(self,"/data/heka_report.json")

        # load latest_values
        latest_values_path = "/tmp/zabbix_hekad_latest_values.json"
        try:
            with open(latest_values_path) as json_file:
                latest_values = simplejson.load(json_file)
        except Exception:
            latest_values = {}

        data = {}
        for output in json['outputs']:
            for indicator in ['SentMessageCount', 'DropMessageCount']:
                if indicator in output.keys():
                    value_key = 'hekad.' + output['Name'] + '.' + indicator;
                    value = output[indicator]['value'];

                    data[value_key + '.total'] = value

                    data[value_key] = value
                    if value_key in latest_values:
                        data[value_key] = value - latest_values[value_key]
                        
                    latest_values[value_key] = value

        # save latest_values
        with open(latest_values_path, 'w') as outfile:
            simplejson.dump(latest_values, outfile)

        data['hekad.zbx_version'] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = HekadServer().run()
    print ret
    sys.exit(ret)