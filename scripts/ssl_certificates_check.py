#!/usr/bin/env python
# -*- coding: utf-8 -*-

import optparse
import yaml
import protobix
import simplejson
import time
import socket
import ssl
import sys
from datetime import datetime

CA_CERTS = "/etc/ssl/certs/ca-certificates.crt"

class SSLEndpointCheck(protobix.SampleProbe):

    __version__ = '0.0.9'

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

    def _parse_args(self):
        # Parse the script arguments
        # Common part
        parser = super( SSLEndpointCheck, self)._parse_args()

        (options, args) = parser.parse_args()
        return (options, args)

    def _init_probe(self):
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host

        ''' Load config file '''
        with open(self.options.config, 'r') as f:
          config = yaml.load(f)
        self.endpoints = config['endpoints']
        self.discovery_key = 'ssl.certificate.discovery'

    def _get_discovery(self):
        data = { self.discovery_key: [] }
        for endpoint in self.endpoints:
            try:
                cert = self._get_certificate( host = endpoint,
                                             port = 443 )
                common_name = cert['subjectAltName'][0][1]
                element = { '{#SSLCERTSERIAL}': common_name + endpoint,
                            '{#SSLCERTNAME}': common_name,
                            '{#SSLCERTENDPOINT}': endpoint }
                data[self.discovery_key].append(element)
            except:
                pass
        return { self.hostname: data }

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
        return { self.hostname: data }

if __name__ == '__main__':
    ret = SSLEndpointCheck().run()
    print ret
    sys.exit(ret)