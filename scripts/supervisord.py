#!/usr/bin/env python
''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Supervisord.
'''
import optparse
import socket
import protobix

import subprocess
import re
import simplejson

__version__ = '0.0.1'
ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

class SupervisorServer(object):

  SUPERV_STAT_CHECK='sudo supervisorctl status'
  supervisor_states = {
    'STOPPED': 0,
    'RUNNING': 0,
    'STOPPING': 1,
    'STARTING': 1,
    'EXITED': 2,
    'BACKOFF': 2,
    'FATAL': 2,
    'UNKNOWN': 2
    }

  def get_infos(self):
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
        worker_list[group_name][proc_name] = {'count': 0,
                                              'STOPPED': 0,
                                              'RUNNING': 0,
                                              'STOPPING': 0,
                                              'STARTING': 0,
                                              'EXITED': 0,
                                              'BACKOFF': 0,
                                              'FATAL': 0,
                                              'UNKNOWN': 0}
      worker_list[group_name][proc_name]['count'] += 1
      worker_list[group_name][proc_name][proc_status] += 1
    return worker_list

  def get_metrics(self):
    data = {}
    try:
      infos = self.get_infos()
      for group in infos:
        for worker in infos[group]:
          for status in infos[group][worker]:
            zbx_key = 'supervisord.worker[{0},{1},{2}]'
            zbx_key = zbx_key.format(group, worker, status)
            data[zbx_key] = infos[group][worker][status]
    except:
      print "CRITICAL: Could not get workers list"
      raise SystemExit, 2
    return data

  def get_discovery(self):
    data = []
    try:
      infos = self.get_infos()
      for group in infos:
        for worker in infos[group]:
          element = { '{#SPVGROUPNAME}': group,
                      '{#SPVWORKERNAME}': worker }
          data.append(element)
    except:
      print "CRITICAL: Could not get workers list"
      raise SystemExit, 2
    return {'supervisord.workers.discovery': data}

def parse_args():
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

    (options, args) = parser.parse_args()

    return (options, args)

def main():

    (options, args) = parse_args()
    hostname = socket.getfqdn()

    try:
        supervisor = SupervisorServer()
    except:
        return 1

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = supervisor.get_metrics()
        data[hostname]['supervisord.zbx_version'] = __version__

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = supervisor.get_discovery()

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
