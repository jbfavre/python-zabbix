#!/usr/bin/env python
# -*- coding: utf-8 -*-

import optparse
import yaml
import protobix
import simplejson
import platform
import time
import socket
import ssl
from datetime import datetime

__version__ = '0.0.1'
CA_CERTS = "/etc/ssl/certs/ca-certificates.crt"

class SSLEndpointCheck(object):

    def __init__(self,conf='ssl_certificates_check.yaml'):
        ''' Load config file '''
        with open(conf, 'r') as f:
          config = yaml.load(f)
        self.endpoints = config['endpoints']

    def exit_error(self, errcode, errtext):
        print errtext
        exit(errcode)

    def check_expiration(self, cert):
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

    def get_certificate(self, HOST, PORT=443):
        # Connect to the host and get the certificate
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        ssl_ctx = ssl.create_default_context(cafile=CA_CERTS)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        ssl_sock = ssl_ctx.wrap_socket(sock, server_hostname=HOST)
        cert = ssl_sock.getpeercert()
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        return cert

    def get_discovery(self):
        discovery_data = { 'ssl.certificate.discovery': []}

        for endpoint in self.endpoints:
            try:
                cert = self.get_certificate(endpoint, 443)
                common_name = cert['subjectAltName'][0][1]
                serial = cert['serialNumber']
                element = { '{#SSLCERTSERIAL}': serial,
                            '{#SSLCERTNAME}': common_name,
                            '{#SSLCERTENDPOINT}': endpoint }
                discovery_data['ssl.certificate.discovery'].append(element)
            except:
                pass

        return discovery_data

    def get_metrics(self):
        data = {}
        for endpoint in self.endpoints:
            try:
                cert = self.get_certificate(endpoint, 443)
                common_name = cert['subjectAltName'][0][1]
                serial = cert['serialNumber']
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
        data['ssl.certificate.zbx_version'] = __version__

        return data

def parse_args():
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

def main():
    (options, args) = parse_args()
    hostname = platform.node()

    ssl_check = SSLEndpointCheck()

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = ssl_check.get_metrics()
    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = ssl_check.get_discovery()

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
