#!/usr/bin/env python
# -*- coding: utf-8 -*-

import optparse
import yaml
import protobix
import simplejson
import time
import socket
import ssl
from datetime import datetime

CA_CERTS = "/etc/ssl/certs/ca-certificates.crt"

class SSLEndpointCheck(protobix.DataContainer):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

    def run(self, conf='/etc/zabbix/ssl_certificates_check.yaml'):
        ''' parse command line options '''
        (options, args) = self._parse_args()
        hostname = socket.getfqdn()

        ''' Load config file '''
        with open(conf, 'r') as f:
          config = yaml.load(f)
        self.endpoints = config['endpoints']

        data = {}
        if options.mode == "update_items":
            self.data_type = 'items'
            data[hostname] = self._get_metrics()
        elif self.options.mode == "discovery":
            data_type = 'lld'
            data[hostname] = self._get_discovery()

        self.add(data)
        self.zbx_host = options.zabbix_server
        self.zbx_port = int(options.zabbix_port)
        self.debug = options.debug
        self.dryrun = options.dry

        try:
            zbx_response = self.send()
        except protobix.SenderException as zbx_exception:
            if self.debug:
                print self.ZBX_CONN_ERR % zbx_exception.err_text
            return 2
        else:
            return 0

    def _check_expiration(self, cert):
        ''' Return the numbers of day before expiration. False if expired. '''
        if 'notAfter' in cert:
            try:
                expire_date = datetime.strptime(cert['notAfter'],
                                                "%b %d %H:%M:%S %Y %Z")
            except:
                exit_error(1, 'Certificate date format unknow.')
            expire_in = expire_date - datetime.now()
            if expire_in.days > 0:
                return expire_in.days
            else:
                return False

    def _get_certificate(self, host, port=443):
        # Connect to the host and get the certificate
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        ssl_sock = ssl.wrap_socket(sock, cert_reqs=ssl.CERT_REQUIRED,
                                   ca_certs=CA_CERTS)
        cert = ssl_sock.getpeercert()
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        return cert

    def _get_discovery(self):
        discovery_data = { 'ssl.certificate.discovery': [] }
        for endpoint in self.endpoints:
            try:
                cert = self._get_certificate( host = endpoint,
                                             port = 443 )
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
                cert = self._get_certificate( host = endpoint,
                                             port = 443 )
                common_name = cert['subjectAltName'][0][1]
                zbx_key = "ssl.certificate.expires_in_days[{0},{1}]"
                zbx_key = zbx_key.format(common_name, endpoint)
                data[zbx_key] = self._check_expiration(cert)

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
        # Parse the script arguments
        # Common part
        parser = optparse.OptionParser()

        parser.add_option(
            '-d', '--dry', action='store_true', default = False,
            help='Performs SSL certificates checks but do not send '
                 'anything to the Zabbix server. Can be used '
                 'for both Update & Discovery mode')
        parser.add_option(
            '-D', '--debug', action='store_true', default = False,
            help='Enable debug mode. This will prevent bulk send '
                 'operations and force sending items one after the '
                 'other, displaying result for each one')

        zabbix_options = optparse.OptionGroup(parser, 'Zabbix configuration')
        zabbix_options.add_option(
            '--zabbix-server', metavar='HOST', default='127.0.0.1',
            help='The hostname of Zabbix server or '
                 'proxy, default is 127.0.0.1.')
        zabbix_options.add_option(
            '--zabbix-port', metavar='PORT', default=10051,
            help='The port on which the Zabbix server or '
                 'proxy is running, default is 10051.')
        zabbix_options.add_option(
            '--update-items', action='store_const',
            dest='mode', const='update_items',
            help='Get & send items to Zabbix. This is the default '
                 'behaviour even if option is not specified')
        zabbix_options.add_option(
            '--discovery', action='store_const',
            dest='mode', const='discovery',
            help='If specified, will perform Zabbix Low Level '
                 'Discovery against domain names to check')
        parser.add_option_group(zabbix_options)
        parser.set_defaults(mode='update_items')

        (options, args) = parser.parse_args()

        return (options, args)

if __name__ == '__main__':
    ret = SSLEndpointCheck().run(conf='ssl_certificates_check.yaml')
    print ret