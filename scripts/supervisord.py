#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Supervisord.
'''
import optparse
import socket
import subprocess
import simplejson
import re
import sys
import protobix


class SupervisorServer(object):

    __version__ = '0.0.8'
    ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

    SUPERV_STAT_CHECK='sudo supervisorctl status'
    SUPERV_STATES = {
        'STOPPED': 0,
        'RUNNING': 0,
        'STOPPING': 1,
        'STARTING': 1,
        'EXITED': 2,
        'BACKOFF': 2,
        'FATAL': 2,
        'UNKNOWN': 2
    }

    def _get_infos(self):
        proc = subprocess.Popen(['/usr/bin/sudo', '/usr/bin/supervisorctl', 'status'], stdout=subprocess.PIPE)
        worker_list = {}
        for line in iter(proc.stdout.readline,''):
            proc_fullname = line.split()[0]
            group_name = proc_fullname.split(':')[0]
            proc_name = proc_fullname.split(':')[1]
            proc_name = re.sub('_\d+', '', proc_name)
            proc_status = line.split()[1]
            if group_name not in worker_list:
                worker_list[group_name] = {}
            if proc_name not in worker_list[group_name]:
                worker_list[group_name][proc_name] = {
                    'count': 0,
                    'STOPPED': 0,
                    'RUNNING': 0,
                    'STOPPING': 0,
                    'STARTING': 0,
                    'EXITED': 0,
                    'BACKOFF': 0,
                    'FATAL': 0,
                    'UNKNOWN': 0
                }
            worker_list[group_name][proc_name]['count'] += 1
            worker_list[group_name][proc_name][proc_status] += 1
        return worker_list

    def _get_metrics(self):
        data = {}
        try:
            infos = self._get_infos()
            for group in infos:
                for worker in infos[group]:
                    for status in infos[group][worker]:
                        zbx_key = 'supervisord.worker[{0},{1},{2}]'
                        zbx_key = zbx_key.format(group, worker, status)
                        data[zbx_key] = infos[group][worker][status]
        except:
            print "CRITICAL: Could not get workers list"
            raise Exception('Fail to get supervisord infos')
        return data

    def _get_discovery(self):
        data = []
        try:
            infos = self._get_infos()
            for group in infos:
                for worker in infos[group]:
                    element = { '{#SPVGROUPNAME}': group,
                                '{#SPVWORKERNAME}': worker }
                    data.append(element)
        except:
            print "CRITICAL: Could not get workers list"
            raise Exception('Fail to get supervisord infos')
        return {'supervisord.workers.discovery': data}

    def _parse_args(self):
        ''' Parse the script arguments
        '''
        parser = optparse.OptionParser()

        parser.add_option("-d", "--dry", action="store_true",
                              help="Performs Supervisord calls but do not send "
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
                                   "Discovery on Supervisord. "
                                   "Default is to get & send items")
        parser.add_option_group(mode_group)
        parser.set_defaults(mode="update_items")

        general_options = optparse.OptionGroup(parser, "Supervisord "
                                                       "configuration options")

        parser.add_option_group(general_options)

        zabbix_options = optparse.OptionGroup(parser, "Zabbix configuration")
        zabbix_options.add_option("--zabbix-server", metavar="HOST", default="localhost",
                                   help="The hostname of Zabbix server or "
                                        "proxy, default is localhost.")
        zabbix_options.add_option("--zabbix-port", metavar="PORT", default=10051,
                                   help="The port on which the Zabbix server or "
                                        "proxy is running, default is 10051.")
        parser.add_option_group(zabbix_options)

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

    def run(self):
        (self.options, args) = self._parse_args()
        hostname = socket.getfqdn()

        # Step 1: init container
        try:
            zbx_container = self._init_container()
        except:
            return 1

        # Step 2: get data
        try:
            data = {}
            if self.options.mode == "update_items":
                zbx_container.set_type("items")
                data[hostname] = self._get_metrics()
                data[hostname]['supervisord.zbx_version'] = self.__version__

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
    ret = SupervisorServer().run()
    print ret
    sys.exit(ret)