#!/usr/bin/env python

# -*- coding: utf-8 -*-

import socket
import csv
import optparse
import protobix
import select

from time import time
from traceback import format_exc

__version__="0.0.1"

class TimeoutException(Exception): 
	pass 

class HAProxyServer(object):
  """ Used for communicating with HAProxy through its local UNIX socket interface.
  """
  def __init__(self, socket_name=None):
    self.socket_name = socket_name
    self.discovery_key = "haproxy_server.pools.discovery"

  def _get_options(self,v):
    options = {
      "1.3": (
        { "hap_proxy_name": False },
        { "hap_sv_name": False },
        { "hap_qcur": True },
        { "hap_qmax": True },
        { "hap_scur": True },
        { "hap_smax": True },
        { "hap_slim": False },
        { "hap_stot": True },
        { "hap_bin": True },
        { "hap_bout": True },
        { "hap_dreq": False },
        { "hap_dresp": False },
        { "hap_ereq": False },
        { "hap_econ": False },
        { "hap_eresp": False },
        { "hap_wretr": False },
        { "hap_wredis": False },
        { "hap_status": True },
        { "hap_weight": False },
        { "hap_act": False },
        { "hap_bck": False },
        { "hap_chkfail": False },
        { "hap_chkdown": False },
        { "hap_lastchg": False },
        { "hap_downtime": False },
        { "hap_qlimit": False },
        { "hap_pid": False },
        { "hap_iid": False },
        { "hap_sid": False },
        { "hap_throttle": False },
        { "hap_lbtot": False },
        { "hap_tracked": False },
        { "hap_type": False },
        { "hap_rate": False },
        { "hap_rate_lim": False },
        { "hap_rate_max": False },
        { "Null": False }
      ),
      "1.4": (
        { "hap_proxy_name": False },
        { "hap_sv_name": False },
        { "hap_qcur": True },
        { "hap_qmax": True },
        { "hap_scur": True },
        { "hap_smax": True },
        { "hap_slim": False },
        { "hap_stot": True },
        { "hap_bin": True },
        { "hap_bout": True },
        { "hap_dreq": False },
        { "hap_dresp": False },
        { "hap_ereq": True },
        { "hap_econ": True },
        { "hap_eresp": True },
        { "hap_wretr": False },
        { "hap_wredis": False },
        { "hap_status": True },
        { "hap_weight": False },
        { "hap_act": False },
        { "hap_bck": False },
        { "hap_chkfail": False },
        { "hap_chkdown": False },
        { "hap_lastchg": False },
        { "hap_downtime": False },
        { "hap_qlimit": False },
        { "hap_pid": False },
        { "hap_iid": False },
        { "hap_sid": False },
        { "hap_throttle": False },
        { "hap_lbtot": False },
        { "hap_tracked": False },
        { "hap_type": False },
        { "hap_rate": False },
        { "hap_rate_lim": False },
        { "hap_rate_max": False },
        { "hap_check_status": True },
        { "hap_check_code": True },
        { "hap_check_duration": True },
        { "hap_hrsp_1xx": True },
        { "hap_hrsp_2xx": True },
        { "hap_hrsp_3xx": True },
        { "hap_hrsp_4xx": True },
        { "hap_hrsp_5xx": True },
        { "hap_hrsp_other": True },
        { "hap_hanafail": False },
        { "hap_req_rate": False },
        { "hap_req_rate_max": False },
        { "hap_req_tot": False },
        { "hap_cli_abrt": False },
        { "hap_srv_abrt": False },
        { "Null": False }
      ),
      "1.5": (
        { "pxname": False },
        { "svname": False },
        { "qcur": True },
        { "qmax": True },
        { "scur": True },
        { "smax": True },
        { "slim": False },
        { "stot": True },
        { "bin": True },
        { "bout": True },
        { "dreq": False },
        { "dresp": False },
        { "ereq": True },
        { "econ": True },
        { "eresp": True },
        { "wretr": False },
        { "wredis": False },
        { "status": True },
        { "weight": False },
        { "act": False },
        { "bck": False },
        { "chkfail": False },
        { "chkdown": False },
        { "lastchg": False },
        { "downtime": False },
        { "qlimit": False },
        { "pid": False },
        { "iid": False },
        { "sid": False },
        { "throttle": False },
        { "lbtot": False },
        { "tracked": False },
        { "type": False },
        { "rate": False },
        { "rate_lim": False },
        { "rate_max": False },
        { "check_status": True },
        { "check_code": True },
        { "check_duration": True },
        { "hrsp_1xx": True },
        { "hrsp_2xx": True },
        { "hrsp_3xx": True },
        { "hrsp_4xx": True },
        { "hrsp_5xx": True },
        { "hrsp_other": True },
        { "hanafail": False },
        { "req_rate": False },
        { "req_rate_max": False },
        { "req_tot": False },
        { "cli_abrt": False },
        { "srv_abrt": False },
        { "comp_in": False },
        { "comp_out": False },
        { "comp_byp": False },
        { "comp_rsp": False },
        { "lastsess": False },
        { "last_chk": False },
        { "last_agt": False },
        { "qtime": False },
        { "ctime": False },
        { "rtime": False },
        { "ttime": False },
        { "Null": False }
      )
    }
    return options[v[:3]]

  def _execute_(self, command, timeout=200):
    """ Executes a HAProxy command by sending a message to a HAProxy's local
    UNIX socket and waiting up to 'timeout' milliseconds for the response.
    """

    buffer = ""

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(self.socket_name)

    client.send(command + "\n")

    running = True
    while(running):
      r, w, e = select.select([client,],[],[], timeout)

      if not (r or w or e):
        raise TimeoutException()

      for s in r:
        if (s is client):
          buffer = buffer + client.recv(16384)
          running = (len(buffer)==0)

    client.close()
    return buffer.decode('utf-8')

  def _get_version(self):
    buffer = self._execute_(command='show info')
    buffer = buffer.strip()
    lines = buffer.split('\n')
    self.info = dict(row.strip().split(':', 1) for row in lines )
    return self.info['Version'].strip()

  def _get_data(self):
    def get_output_key(index):
        return index.keys()[0]
    hap_version = self._get_version()
    buffer = self._execute_('show stat')
    buffer = buffer.lstrip('# ')
    csv_stat = csv.DictReader(buffer.split(',\n'))
    data = {}
    for row in csv_stat:
      if row['pxname'] not in data:
        data[row['pxname']] = { }
      if row['svname'] in ['FRONTEND']:
        options_list = self._get_options(hap_version)
        pool_stats = {}
        for i in range(0,len(options_list)):
            key = get_output_key(options_list[i])
            if options_list[i][key] is True:
                pool_stats[key] = row[key]
        data[row['pxname']] = pool_stats
    return data

  def get_metrics(self):
    raw_data = self._get_data()
    data = {}
    for pxname in raw_data:
      for metric in raw_data[pxname]:
        if raw_data[pxname][metric] == '':
          raw_data[pxname][metric] = 0
        if metric == 'status' and raw_data[pxname][metric] == 'OPEN':
          raw_data[pxname][metric] = 1
        elif metric == 'status':
          raw_data[pxname][metric] = 0
        zbx_key = 'haproxy_server.pool[{0},{1}]'
        zbx_key = zbx_key.format(pxname,metric)
        data[zbx_key] = raw_data[pxname][metric]
    data["haproxy_server.zbx_version"] = __version__
    return data

  def get_discovery(self):
    raw_data = self._get_data()
    data = {
        self.discovery_key:[],
    }
    for pxname in raw_data:
      element = { '{#HAPPOOLNAME}': pxname }
      data[self.discovery_key].append(element)
    return data
    

def parse_args():
    ''' Parse the script arguments'''
    parser = optparse.OptionParser()

    parser.add_option("-d", "--dry", action="store_true",
                          help="Performs Haproxy stats call but do not send "
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
                               "Discovery on Haproxy. "
                               "Default is to get & send items")
    parser.add_option_group(mode_group)
    parser.set_defaults(mode="update_items")

    general_options = optparse.OptionGroup(parser, "Haproxy Configuration")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="Haproxy server hostname")
    general_options.add_option("-p", "--port", help="Haproxy stats port", default=1936)
    general_options.add_option('--username', help='Haproxy stats username',
                      default='zabbix')
    general_options.add_option('--password', help='Haproxy stats password',
                      default='zabbix')
    general_options.add_option('--uri', help='Haproxy stats URI',
                      default='')
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
        hostname = socket.getfqdn()
    else:
        hostname = options.host

    try:
        hap = HAProxyServer('/run/haproxy.socket')
    except:
        return 1

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = hap.get_metrics()

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = hap.get_discovery()

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
