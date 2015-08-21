#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration SSL endpoints.
'''
import optparse
import yaml
import protobix
import simplejson
import time
import socket
import ssl
import sys
from datetime import datetime

class SSLEndpointCheck(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

    CA_CERTS = "/etc/ssl/certs/ca-certificates.crt"

    def _check_expiration(self, cert):
        ''' Return the numbers of day before expiration. False if expired. '''
        if 'notAfter' in cert:
            try:
                expire_date = datetime.strptime(cert['notAfter'],
                                                "%b %d %H:%M:%S %Y %Z")
            except:
                raise Exception('Certificate date format unknow.')
            expire_in = expire_date - datetime.now()
            if expire_in.days > 0:
                return expire_in.days
            else:
                return False

    def _get_certificate(self, HOST, PORT=443):
        # Connect to the host and get the certificate
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        ssl_sock = ssl.wrap_socket(sock, cert_reqs=ssl.CERT_REQUIRED,
                                   ca_certs=CA_CERTS)
        cert = ssl_sock.getpeercert()
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        return cert

    def _get_discovery(self):
        discovery_data = { 'ssl.certificate.discovery': []}

        for endpoint in self.endpoints:
            try:
                cert = self._get_certificate(endpoint, 443)
                common_name = cert['subjectAltName'][0][1]
                element = { '{#SSLCERTSERIAL}': common_name + endpoint,
                            '{#SSLCERTNAME}': common_name,
                            '{#SSLCERTENDPOINT}': endpoint }
                discovery_data['ssl.certificate.discovery'].append(element)
            except:
                pass

        return discovery_data

    def _get_metrics(self):
        data = {}
        for endpoint in self.endpoints:
            try:
                cert = self.get_certificate(endpoint, 443)
                common_name = cert['subjectAltName'][0][1]
                zbx_key = "ssl.certificate.expires_in_days[{0},{1}]"
                zbx_key = zbx_key.format(common_name, endpoint)
                data[zbx_key] = self.check_expiration(cert)

                zbx_key = "ssl.certificate.check_status[{0}]"
                zbx_key = zbx_key.format(endpoint)
                data[zbx_key] = 1
            except:
                zbx_key = "ssl.certificate.check_status[{0}]"
                zbx_key = zbx_key.format(endpoint)
                data[zbx_key] = 0
                pass
        data['ssl.certificate.zbx_version'] = self.__version__

        return data

    def _parse_args(self):
        ''' Parse the script arguments'''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs SSL certificates checks but do not send "
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
                                   "Discovery against domain names to check. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

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

    def _init_container(self):
        zbx_container = protobix.DataContainer(
            data_type = 'items',
            zbx_host  = self.options.zabbix_server,
            zbx_port  = int(self.options.zabbix_port),
            debug     = self.options.debug,
            dryrun    = self.options.dry
        )
        return zbx_container

    def run(self, conf_file='/etc/zabbix/ssl_certificates_check.yaml'):
        (self.options, args) = self._parse_args()
        hostname = socket.getfqdn()

        # Step 1: init container
        try:
            zbx_container = self._init_container()
        except:
            return 1

        # Step 2: get data
        try:
            ''' Load config file '''
            with open(conf_file, 'r') as f:
                config = yaml.load(f)
            self.endpoints = config['endpoints']

            data = {}
            if self.options.mode == "update_items":
                zbx_container.set_type("items")
                data[hostname] = self._get_metrics()
            elif self.options.mode == "discovery":
                zbx_container.set_type("lld")
                data[hostname] = self._get_discovery()
        except:
            return 2

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
    ret = SSLEndpointCheck().run()
    print ret
    sys.exit(ret)
