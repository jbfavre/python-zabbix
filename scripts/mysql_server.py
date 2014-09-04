#!/usr/bin/env python
'''
    Copyright (c) 2014 Jean Baptiste Favre.
    Sample script for Zabbix integration with MySQL / MariaDB.
'''

import mysql.connector
import optparse
import json
import platform
import protobix

__version__ = '0.0.2'
ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

# MariaDB 10.0 slave key's list
replication_keys=['connection_name','slave_sql_state','slave_io_state','master_host','master_user','master_port','connect_retry','master_log_file','read_master_log_pos','relay_log_file','relay_log_pos','relay_master_log_file','slave_io_running','slave_sql_running','replicate_do_db','replicate_ignore_db','replicate_do_table','replicate_ignore_table','replicate_wild_do_table','replicate_wild_ignore_table','last_errno','last_error','skip_counter','exec_master_log_pos','relay_log_space','until_condition','until_log_file','until_log_pos','master_ssl_allowed','master_ssl_ca_file','master_ssl_ca_path','master_ssl_cert','master_ssl_cipher','master_ssl_key','seconds_behind_master','master_ssl_verify_server_cert','last_io_errno','last_io_error','last_sql_errno','last_sql_error','replicate_ignore_server_ids','master_server_id','master_ssl_crl','master_ssl_crlpath','using_gtid','gtid_io_pos','retried_transactions','max_relay_log_size','executed_log_entries','slave_received_heartbeats','slave_heartbeat_period','gtid_slave_pos']

MYSQL_REPLICATION_MAPPING = {"Yes": 1, "No": 0}

class MysqlAPI(object):

    def __init__(self, user_name='guest', password='guest',
                 host_name='', port=3306, database='mysql'):
        self.config = {
          'user': user_name,
          'password': password,
          'host': host_name,
          'database': database
        }

        self.discovery_key = "mysql.replication.discovery"
        self.cnx = mysql.connector.connect(**self.config)

    def get_all_slaves_status(self):
        cursor = self.cnx.cursor()
        cursor.execute("SHOW ALL SLAVES STATUS")
        replication_list=[]
        for (replication_item) in cursor:
          replication_list.append(dict(zip(replication_keys,replication_item)))
        return replication_list

    def get_discovery(self):
        data = {self.discovery_key:[]}
        for replication in self.get_all_slaves_status():
          replication_name=replication['connection_name']
          if(replication['connection_name']==""):
            replication_name=replication['master_host']
          data[self.discovery_key].append({'{#MYSQLREPNAME}': replication_name})
        return data

    def get_metrics(self):
        data = {self.discovery_key:[]}
        replication_list=self.get_all_slaves_status()
        zbx_key = "mysql.replication.sources"
        data[zbx_key] = len(replication_list)
        for replication in replication_list:

          replication_name=replication['connection_name']
          if(replication['connection_name']==""):
            replication_name=replication['master_host']

          master_files_diff=0
          if(replication['master_log_file'] != replication['relay_master_log_file']):
            master_files_diff = 1
          zbx_key = "mysql.replication[{0},master_files_diff]"
          zbx_key = zbx_key.format(replication_name)
          data[zbx_key] = master_files_diff

          for item in ['slave_io_running','slave_sql_running','using_gtid']:
            zbx_key = "mysql.replication[{0},{1}]"
            zbx_key = zbx_key.format(replication_name, item)
            data[zbx_key] = MYSQL_REPLICATION_MAPPING[replication[item]]

          for item in [ 'last_errno', 'last_io_errno', 'last_sql_errno',
                        'read_master_log_pos','exec_master_log_pos',
                        'seconds_behind_master']:
            zbx_key = "mysql.replication[{0},{1}]"
            zbx_key = zbx_key.format(replication_name, item)
            data[zbx_key] = replication[item]

        data["mysql.zbx_version"] = __version__
        return data

def parse_args():
    ''' Parse the script arguments'''
    parser = optparse.OptionParser()

    parser.add_option("-d", "--dry", action="store_true",
                          help="Performs MySQL calls but do not send "
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
                               "Discovery on MySQL. "
                               "Default is to get & send items")
    parser.add_option_group(mode_group)
    parser.set_defaults(mode="update_items")

    general_options = optparse.OptionGroup(parser, "MySQL Configuration")
    general_options.add_option("-H", "--host", metavar="HOST", default="localhost",
                               help="MySQL server hostname")
    general_options.add_option("-p", "--port", help="MySQL server  port", default=15672)
    general_options.add_option('--username', help='MySQL server username',
                      default='zabbix')
    general_options.add_option('--password', help='MySQL server password',
                      default='zabbix')
    general_options.add_option('--database', help='MySQL server database',
                      default='mysql')
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
        hostname = platform.node()
    else:
        hostname = options.host

    try:
        obj = MysqlAPI(user_name=options.username,
                       password=options.password,
                       host_name=hostname,
                       port=options.port,
                       database=options.database)
    except:
        return 1

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = obj.get_metrics()

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = obj.get_discovery()

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
