#!/usr/bin/env python
'''
    Copyright (c) 2014 Jean Baptiste Favre.
    Sample script for Zabbix integration with MySQL / MariaDB.
'''

import optparse
import json
import platform
import protobix

import mysql.connector
import re

__version__ = '0.0.3'
ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

# MariaDB 10.0 slave key's list
# WARNING
# Order is important !!!
replication_keys=[
    'connection_name',
    'slave_sql_state',
    'slave_io_state',
    'master_host',
    'master_user',
    'master_port',
    'connect_retry',
    'master_log_file',
    'read_master_log_pos',
    'relay_log_file',
    'relay_log_pos',
    'relay_master_log_file',
    'slave_io_running',
    'slave_sql_running',
    'replicate_do_db',
    'replicate_ignore_db',
    'replicate_do_table',
    'replicate_ignore_table',
    'replicate_wild_do_table',
    'replicate_wild_ignore_table',
    'last_errno',
    'last_error',
    'skip_counter',
    'exec_master_log_pos',
    'relay_log_space',
    'until_condition',
    'until_log_file',
    'until_log_pos',
    'master_ssl_allowed',
    'master_ssl_ca_file',
    'master_ssl_ca_path',
    'master_ssl_cert',
    'master_ssl_cipher',
    'master_ssl_key',
    'seconds_behind_master',
    'master_ssl_verify_server_cert',
    'last_io_errno',
    'last_io_error',
    'last_sql_errno',
    'last_sql_error',
    'replicate_ignore_server_ids',
    'master_server_id',
    'master_ssl_crl',
    'master_ssl_crlpath',
    'using_gtid',
    'gtid_io_pos',
    'retried_transactions',
    'max_relay_log_size',
    'executed_log_entries',
    'slave_received_heartbeats',
    'slave_heartbeat_period',
    'gtid_slave_pos'
]

wsrep_status_keys=[
    'apply_oooe',
    'apply_oool',
    'apply_window',
    'cert_deps_distance',
    'cluster_size',
    'commit_oooe',
    'commit_oool',
    'commit_window',
    'flow_control_paused',
    'flow_control_recv',
    'flow_control_sent',
    'local_bf_aborts',
    'local_cert_failures',
    'local_commit',
    'local_index',
    'local_recv_queue',
    'local_replays',
    'local_send_queue',
    'received',
    'received_bytes',
    'replicated',
    'replicated_bytes',
    'thread_count'
]

status_bl = [
    'binlog_bytes_written',
    'binlog_cache_disk_use',
    'binlog_cache_use',
    'binlog_commits',
    'binlog_group_commits',
    'binlog_snapshot_file',
    'binlog_snapshot_position',
    'binlog_stmt_cache_disk_use',
    'binlog_stmt_cache_use',
    'com_show_client_statistics',
    'com_show_collations',
    'com_show_contributors',
    'com_show_create_db',
    'com_show_create_event',
    'com_show_create_func',
    'com_show_create_proc',
    'com_show_create_table',
    'com_show_create_trigger',
    'com_show_databases',
    'com_show_engine_logs',
    'com_show_engine_mutex',
    'com_show_engine_status',
    'com_show_errors',
    'com_show_events',
    'com_show_explain',
    'com_show_fields',
    'com_show_function_status',
    'com_show_grants',
    'com_show_index_statistics',
    'com_show_keys',
    'com_show_master_status',
    'com_show_open_tables',
    'com_show_plugins',
    'com_show_privileges',
    'com_show_procedure_status',
    'com_show_processlist',
    'com_show_profile',
    'com_show_profiles',
    'com_show_relaylog_events',
    'com_show_slave_hosts',
    'com_show_slave_status',
    'com_show_status',
    'com_show_storage_engines',
    'com_show_tables',
    'com_show_table_statistics',
    'com_show_table_status',
    'com_show_triggers',
    'com_show_user_statistics',
    'com_show_variables',
    'com_show_warnings',
    'com_start_all_slaves',
    'com_start_slave',
    'com_stop_all_slaves',
    'com_stop_slave',
    'performance_schema_accounts_lost',
    'performance_schema_cond_classes_lost',
    'performance_schema_cond_instances_lost',
    'performance_schema_digest_lost',
    'performance_schema_file_classes_lost',
    'performance_schema_file_handles_lost',
    'performance_schema_file_instances_lost',
    'performance_schema_hosts_lost',
    'performance_schema_locker_lost',
    'performance_schema_mutex_classes_lost',
    'performance_schema_mutex_instances_lost',
    'performance_schema_rwlock_classes_lost',
    'performance_schema_rwlock_instances_lost',
    'performance_schema_session_connect_attrs_lost',
    'performance_schema_socket_classes_lost',
    'performance_schema_socket_instances_lost',
    'performance_schema_stage_classes_lost',
    'performance_schema_statement_classes_lost',
    'performance_schema_table_handles_lost',
    'performance_schema_table_instances_lost',
    'performance_schema_thread_classes_lost',
    'performance_schema_thread_instances_lost',
    'performance_schema_users_lost',
    'ssl_accept_renegotiates',
    'ssl_accepts',
    'ssl_callback_cache_hits',
    'ssl_client_connects',
    'ssl_connect_renegotiates',
    'ssl_ctx_verify_depth',
    'ssl_ctx_verify_mode',
    'ssl_default_timeout',
    'ssl_finished_accepts',
    'ssl_finished_connects',
    'ssl_session_cache_hits',
    'ssl_session_cache_misses',
    'ssl_session_cache_mode',
    'ssl_session_cache_overflows',
    'ssl_session_cache_size',
    'ssl_session_cache_timeouts',
    'ssl_sessions_reused',
    'ssl_used_session_cache_entries',
    'ssl_verify_depth',
    'ssl_verify_mode',
    'opened_plugin_libraries',
    'rpl_status',
    'slave_heartbeat_period',
    'slave_open_temp_tables',
    'slave_received_heartbeats',
    'slave_retried_transactions',
    'slave_running'
]

MYSQL_REPLICATION_MAPPING = { "Yes": 1, "No": 0 }
MYSQL_INNODB_MAPPING = {
    'not started': 0,
    'started': 1,
    'ON': 1,
    'OFF': 1
}

class MysqlServer(object):

    ''' InnoDB class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/optimization-and-tuning/system-variables/xtradbinnodb-server-status-variables/
        Innodb_available_undo_logs : numeric
        Innodb_background_log_sync : numeric
        Innodb_buffer_pool_bytes_data : numeric
        Innodb_buffer_pool_bytes_dirty : numeric
        Innodb_buffer_pool_dump_status : numeric
        Innodb_buffer_pool_load_status : numeric
        Innodb_buffer_pool_pages_data : numeric
        Innodb_buffer_pool_pages_dirty : numeric
        Innodb_buffer_pool_pages_flushed : numeric
        Innodb_buffer_pool_pages_LRU_flushed : numeric
        Innodb_buffer_pool_pages_free : numeric
        Innodb_buffer_pool_pages_made_not_young : numeric
        Innodb_buffer_pool_pages_made_young : numeric
        Innodb_buffer_pool_pages_misc : numeric
        Innodb_buffer_pool_pages_old : numeric
        Innodb_buffer_pool_pages_total : numeric
        Innodb_buffer_pool_read_ahead : numeric
        Innodb_buffer_pool_read_ahead_evicted : numeric
        Innodb_buffer_pool_read_ahead_rnd : numeric
        Innodb_buffer_pool_read_requests : numeric
        Innodb_buffer_pool_reads : numeric
        Innodb_buffer_pool_wait_free : numeric
        Innodb_buffer_pool_write_requests : numeric
        Innodb_checkpoint_age : numeric
        Innodb_checkpoint_max_age : numeric
        Innodb_checkpoint_target_age : numeric
        Innodb_current_row_locks : numeric
        Innodb_data_fsyncs : numeric
        Innodb_data_pending_fsyncs : numeric
        Innodb_data_pending_reads : numeric
        Innodb_data_pending_writes : numeric
        Innodb_data_read : numeric
        Innodb_data_reads : numeric
        Innodb_data_writes : numeric
        Innodb_data_written : numeric
        Innodb_dblwr_pages_written : numeric
        Innodb_dblwr_writes : numeric
        Innodb_deadlocks : numeric
        Innodb_have_atomic_builtins : boolean
        Innodb_history_list_length : numeric
        Innodb_ibuf_discarded_delete_marks : numeric
        Innodb_ibuf_discarded_deletes : numeric
        Innodb_ibuf_discarded_inserts : numeric
        Innodb_ibuf_free_list : numeric
        Innodb_ibuf_merged_delete_marks : numeric
        Innodb_ibuf_merged_deletes : numeric
        Innodb_ibuf_merged_inserts : numeric
        Innodb_ibuf_merges : numeric
        Innodb_ibuf_segment_size : numeric
        Innodb_ibuf_size : numeric
        Innodb_log_waits : numeric
        Innodb_log_write_requests : numeric
        Innodb_log_writes : numeric
        Innodb_lsn_current : numeric
        Innodb_lsn_flushed : numeric
        Innodb_lsn_last_checkpoint : numeric
        Innodb_master_thread_active_loops : numeric
        Innodb_master_thread_idle_loops : numeric
        Innodb_max_trx_id : numeric
        Innodb_mem_adaptive_hash : numeric
        Innodb_mem_dictionary : numeric
        Innodb_mem_total : numeric
        Innodb_mutex_os_waits : numeric
        Innodb_mutex_spin_rounds : numeric
        Innodb_mutex_spin_waits : numeric
        Innodb_num_open_files : numeric
        Innodb_oldest_view_low_limit_trx_id : numeric
        Innodb_os_log_fsyncs : numeric
        Innodb_os_log_pending_fsyncs : numeric
        Innodb_os_log_pending_writes : numeric
        Innodb_os_log_written : numeric
        Innodb_page_size : numeric
        Innodb_pages_created : numeric
        Innodb_pages_read : numeric
        Innodb_pages_written : numeric
        Innodb_purge_trx_id : numeric
        Innodb_purge_undo_no : numeric
        Innodb_read_views_memory : numeric
        Innodb_row_lock_current_waits : numeric
        Innodb_row_lock_time : numeric
        Innodb_row_lock_time_avg : decimal
        Innodb_row_lock_time_max : numeric
        Innodb_row_lock_time_waits : decimal
        Innodb_rows_deleted : numeric
        Innodb_rows_inserted : numeric
        Innodb_rows_read : numeric
        Innodb_rows_updated : numeric
        Innodb_s_lock_os_waits : numeric
        Innodb_s_lock_spin_rounds : numeric
        Innodb_s_lock_spin_waits : numeric
        Innodb_truncated_status_writes : numeric
        Innodb_x_lock_os_waits : numeric
        Innodb_x_lock_spin_rounds : numeric
        Innodb_x_lock_spin_waits : numeric
    '''
    class Innodb(object):

        def __init__(self, server):
            self.server = server
            self.key_prefix = 'innodb'
            self.status_prefix = 'Innodb_'

        def _parser(self, lines):
            data = {}
            header = False # keep simple state of if we are in a header or not
            headerStr = ""
            bodyList = []
            for line in lines:
                line = line.strip()
                if line.startswith('END OF INNODB MONITOR OUTPUT'):
                    return data
                if re.match(r'^-+$', line):
                    header = not header
                    if headerStr:
                        data[headerStr] = bodyList
                        bodyList = []
                else:
                    if header:
                        headerStr = line
                    else:
                        bodyList.append(line)

            # Shouldn't really get here
            return data

        def _buffer_memory_parser(self, lines):
            result = {}
            for line in lines:
                ''' Example:
                    Total memory allocated 38972620800; in additional pool allocated 0
                    Total memory allocated by read views 1264
                '''
                pattern='^Total memory allocated (\d+); in additional pool allocated (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['total_mem_alloc'] = int(m.group(1))
                    result['additional_pool_alloc'] = int(m.group(2))
                ''' Example:
                    Adaptive hash index 3369597072 	(602892328 + 2766704744)
                '''
                pattern='^Adaptive hash index (\d*).*$'
                m = re.search(pattern, line)
                if m:
                    result['adaptive_hash_memory'] = int(m.group(1))
                ''' Example:
                    Page hash           3140888 (buffer pool 0 only)
                '''
                pattern='^Page hash\s+(\d+).*$'
                m = re.search(pattern, line)
                if m:
                    result['page_hash_memory'] = int(m.group(1))
                ''' Example:
                    Dictionary cache    153440970 	(150724592 + 2716378)
                '''
                pattern='^Dictionary cache\s+(\d+)\s+\(\d+ \+ \d+\)$'
                m = re.search(pattern, line)
                if m:
                    result['dictionary_cache_memory'] = int(m.group(1))
                ''' Example:
                    File system         1032976 	(812272 + 220704)
                '''
                pattern='^File system\s+(\d+) 	\(\d+ \+ \d+\)$'
                m = re.search(pattern, line)
                if m:
                    result['file_system_memory'] = int(m.group(1))
                ''' Example:
                    Lock system         94209256 	(94203496 + 5760)
                '''
                pattern='^Lock system\s+(\d+) 	\(\d+ \+ \d+\)$'
                m = re.search(pattern, line)
                if m:
                    result['lock_system_memory'] = int(m.group(1))
                ''' Example:
                    Recovery system     0 	(0 + 0)
                '''
                pattern='^Recovery system\s+(\d+) 	\(\d+ \+ \d+\)$'
                m = re.search(pattern, line)
                if m:
                    result['recovery_system_memory'] = int(m.group(1))
                ''' Example:
                    Dictionary memory allocated 2716378
                '''
                ''' Example:
                    Buffer pool size        2324208
                '''
                pattern='^Buffer pool size\s+(\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['pool_size'] = int(m.group(1))
                ''' Example:
                    Buffer pool size, bytes 38079823872
                '''
                ''' Example:
                    Free buffers            12265
                '''
                pattern='^Free buffers\s+(\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['free_pages'] = int(m.group(1))
                ''' Example:
                    Database pages          2143077
                '''
                pattern='^Database pages\s+(\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['database_pages'] = int(m.group(1))
                ''' Example:
                    Old database pages      790857
                '''
                ''' Example:
                    Modified db pages       128001
                '''
                pattern='^Modified db pages\s+(\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['modified_pages'] = int(m.group(1))
                ''' Example:
                    Pending reads 0
                '''
                ''' Example:
                    Pending writes: LRU 0, flush list 0, single page 0
                '''
                ''' Example:
                    Pages made young 168684656, not young 1422812817
                '''
                ''' Example:
                    39.39 youngs/s, 201.91 non-youngs/s
                '''
                ''' Example:
                    Pages read 158403177, created 13432370, written 501462122
                '''
                pattern='^Pages read (\d+), created (\d+), written (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['pages_read'] = int(m.group(1))
                    result['pages_created'] = int(m.group(2))
                    result['pages_written'] = int(m.group(3))
                ''' Example:
                    36.14 reads/s, 1.42 creates/s, 122.14 writes/s
                '''
                ''' Example:
                    Buffer pool hit rate 999 / 1000, young-making rate 1 / 1000 not 7 / 1000
                '''
                ''' Example:
                    Pages read ahead 0.00/s, evicted without access 0.00/s, Random read ahead 0.00/s
                '''
                ''' Example:
                    LRU len: 2143077, unzip_LRU len: 0
                '''
                ''' Example:
                    I/O sum[72384]:cur[672], unzip sum[0]:cur[0]
                '''

            return result

        def _log_parser(self,lines):
            result = {}
            for line in lines:
                ''' Example:
                    Log sequence number 6552935665366
                '''
                pattern='^Log sequence number (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['log_bytes_written'] = int(m.group(1))
                ''' Example:
                    Log flushed up to   6552935647135
                '''
                pattern='^Log flushed up to   (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['log_bytes_flushed'] = int(m.group(1))
                ''' Example:
                    Last checkpoint at  6552701367592
                '''
                pattern='^Last checkpoint at  (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['last_checkpoint'] = int(m.group(1))
                ''' Example:
                    Max checkpoint age    3056933193
                '''
                pattern='^(\d+) pending log writes, (\d+) pending chkp writes$'
                m = re.search(pattern, line)
                if m:
                    result['pending_log_writes'] = int(m.group(1))
                    result['pending_chkp_writes'] = int(m.group(2))
                ''' Example:
                    907870229 log i/o's done, 208.50 log i/o's/second
                '''
                pattern='^(\d+) log i\/o\'s done, ([\.\d]+) log i\/o\'s\/second$'
                m = re.search(pattern, line)
                if m:
                    result['log_writes'] = int(m.group(1))
                    result['log_writes_per_sec'] = m.group(2)

            result['unflushed_log'] = result['log_bytes_written'] - result['log_bytes_flushed']
            result['uncheckpointed_bytes'] = result['log_bytes_written'] - result['last_checkpoint']
            return result

        def _insert_buffer_parser(self,lines):
            result = {}
            prev_line = ''
            for line in lines:
                ''' Example:
                    156510952 OS file reads, 1423853152 OS file writes, 162593695 OS fsyncs
                '''
                pattern = '^(\d+) OS file reads, (\d+) OS file writes, (\d+) OS fsyncs$'
                m = re.search(pattern, line)
                if m:
                    result['file_reads'] = int(m.group(1))
                    result['file_writes'] = int(m.group(2))
                    result['file_fsyncs'] = int(m.group(3))
                ''' Example:
                    Ibuf: size 1, free list len 155, seg size 157, 53030435 merges
                '''
                pattern = '^Ibuf: size (\d+), free list len (\d+), seg size (\d+), (\d+) merges$'
                m = re.search(pattern, line)
                if m:
                    result['ibuf_used_cells'] = int(m.group(1))
                    result['ibuf_free_cells'] = int(m.group(2))
                    result['ibuf_cell_count'] = int(m.group(3))
                    result['ibuf_merges'] = int(m.group(4))
                ''' Example:
                    merged operations:
                    insert 104632411, delete mark 32183433, delete 17962334
                '''
                pattern = '^insert (\d+), delete mark (\d+), delete (\d+)$'
                m = re.search(pattern, line)
                if m and prev_line.startswith('merged operations') :
                    result['ibuf_inserts'] = int(m.group(1))
                    result['ibuf_merged'] = int(m.group(1)) + int(m.group(2)) + int(m.group(3))
                ''' Example:
                    discarded operations:
                    insert 104632411, delete mark 32183433, delete 17962334
                '''
                pattern = '^insert (\d+), delete mark (\d+), delete (\d+)$'
                m = re.search(pattern, line)
                if m and prev_line.startswith('discarded operations') :
                    result['ibuf_discarded_inserts'] = int(m.group(1))
                    result['ibuf_discarded'] = int(m.group(1)) + int(m.group(2)) + int(m.group(2))
                ''' Example:
                    860.41 hash searches/s, 3066.48 non-hash searches/s
                '''
                pattern = '^([\.\d]+) hash searches\/s, ([\.\d]+) non-hash searches\/s$'
                m = re.search(pattern, line)
                if m:
                    result['hash_search_per_sec'] = m.group(1)
                    result['non_hash_search_per_sec'] = m.group(2)

                prev_line=line
            return result

        def _file_io_parser(self,lines):
            result = {}
            for line in lines:
                ''' Example:
                    156510952 OS file reads, 1423853152 OS file writes, 162593695 OS fsyncs
                '''
                pattern = '^(\d+) OS file reads, (\d+) OS file writes, (\d+) OS fsyncs$'
                m = re.search(pattern, line)
                if m:
                    result['file_reads'] = int(m.group(1))
                    result['file_writes'] = int(m.group(2))
                    result['file_fsyncs'] = int(m.group(3))
                ''' Example:
                    Pending normal aio reads: 0 [0, 0, ...] , aio writes: 0 [0, 0, ...] ,
                '''
                pattern = '^Pending normal aio reads: (\d+) .*, aio writes: (\d+)'
                m = re.search(pattern, line)
                if m:
                    result['pending_normal_aio_reads'] = int(m.group(1))
                    result['pending_normal_aio_writes'] = int(m.group(2))
                ''' Example:
                     ibuf aio reads: 0, log i/o's: 0, sync i/o's: 0
                '''
                pattern = '^.*ibuf aio reads: (\d+), log i/o\'s: (\d+), sync i/o\'s: (\d+)'
                m = re.search(pattern, line)
                if m:
                    result['pending_ibuf_aio_reads'] = int(m.group(1))
                    result['pending_aio_log_ios'] = int(m.group(2))
                    result['pending_aio_sync_ios'] = int(m.group(3))
                ''' Example:
                    Pending flushes (fsync) log: 0; buffer pool: 0
                '''
                pattern = '^Pending flushes \(fsync\) log: (\d+); buffer pool: (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['pending_log_flushes'] = int(m.group(1))
                    result['pending_buf_pool_flushes'] = int(m.group(2))
                ''' Example:
                    32.46 reads/s, 16384 avg bytes/read, 403.61 writes/s, 69.54 fsyncs/s
                '''
                pattern = '^([\.\d]+) reads\/s, ([\.\d]+) avg bytes\/read, ([\.\d]+) writes\/s, ([\.\d]+) fsyncs\/s$'
                m = re.search(pattern, line)
                if m:
                    result['reads_per_sec'] = m.group(1)
                    result['avg_bytes_per_read'] = m.group(2)
                    result['writes_per_sec'] = m.group(3)
                    result['fsyncs_per_sec'] = m.group(4)

            return result

        def _row_ops_parser(self,lines):
            result = {}
            for line in lines:
                ''' Examples:
                    0 queries inside InnoDB, 0 queries in queue
                '''
                pattern = '^(\d+) queries inside InnoDB, (\d+) queries in queue$'
                m = re.search(pattern, line)
                if m:
                    result['queries_inside'] = int(m.group(1))
                    result['queries_queued'] = int(m.group(2))
                ''' Examples:
                    0 read views open inside InnoDB
                '''
                pattern = '^Trx id counter (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['read_views'] = int(m.group(1))
                ''' Examples:
                    0 RW transactions active inside InnoDB
                '''
                pattern = '^(\d+) RW transactions active inside InnoDB$'
                m = re.search(pattern, line)
                if m:
                    result['rw_active_transactions'] = int(m.group(1))
                ''' Examples:
                    0 RO transactions active inside InnoDB
                '''
                pattern = '^(\d+) RO transactions active inside InnoDB$'
                m = re.search(pattern, line)
                if m:
                    result['ro_active_transactions'] = int(m.group(1))
                ''' Examples:
                    0 out of 1000 descriptors used
                '''
                pattern = '^(\d+) out of (\d+) descriptors used$'
                m = re.search(pattern, line)
                if m:
                    result['fd_used_percent'] = int(m.group(1))*100/int(m.group(2))
                ''' Examples:
                    Number of rows inserted 1084763204, updated 665213995, deleted 438410944, read 7659578616
                '''
                pattern = '^Number of rows inserted (\d+), updated (\d+), deleted (\d+), read (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['row_inserted'] = int(m.group(1))
                    result['row_updated'] = int(m.group(2))
                    result['row_deleted'] = int(m.group(3))
                    result['row_read'] = int(m.group(4))
                ''' Examples:
                    268.24 inserts/s, 137.66 updates/s, 195.83 deletes/s, 824.59 reads/s
                '''
                pattern = '^([\.\d]+) inserts\/s, ([\.\d]+) updates\/s, ([\.\d]+) deletes\/s, ([\.\d]+) reads\/s$'
                m = re.search(pattern, line)
                if m:
                    result['insert_per_sec'] = m.group(1)
                    result['update_per_sec'] = m.group(2)
                    result['delete_per_sec'] = m.group(3)
                    result['read_per_sec'] = m.group(4)

            return result

        def _transactions_parser(self,lines):
            result = {
                'current_transactions': 0,
                'active_transactions': 0
            }
            for line in lines:
                ''' Example:
                    Trx id counter 18594322142
                '''
                pattern = '^Trx id counter (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['innodb_transactions'] = int(m.group(1))
                ''' Example:
                    Purge done for trx's n:o < 18594381626 undo n:o < 0 state: running but idle
                '''
                pattern = '^Purge done for trx\'s n:o < (\d+)'
                m = re.search(pattern, line)
                if m:
                    result['purged_txns'] = int(m.group(1))
                ''' Example:
                    History list length 2219
                '''
                pattern = '^History list length (\d+)'
                m = re.search(pattern, line)
                if m:
                    result['history_list'] = int(m.group(1))
                ''' Example:
                    ---TRANSACTION 16559480579, not started
                    ---TRANSACTION 18594537673, ACTIVE 0 sec committing
                '''
                pattern = '^---TRANSACTION (\d+), (\w+)'
                m = re.search(pattern, line)
                if m:
                    result['current_transactions'] += 1
                    if m.group(1).startswith('ACTIVE'):
                      result['active_transactions'] += 1

            result['unpurged_txns'] = result['innodb_transactions'] - result['purged_txns']
            return result

        def _semaphores_parser(self,lines):
            result = {
                'spin_waits': 0,
                'spin_rounds' : 0,
                'os_waits': 0
            }
            for line in lines:
                ''' Example:
                    Mutex spin waits 79626940, rounds 157459864, OS waits 698719
                '''
                pattern = '^Mutex spin waits (\d+), rounds (\d+), OS waits (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['spin_waits']+=int(m.group(1))
                    result['spin_rounds']+=int(m.group(2))
                    result['os_waits']+=int(m.group(3))

                ''' Example: Pre 5.5.17 SHOW ENGINE INNODB STATUS syntax
                    RW-shared spins 3859028, OS waits 2100750; RW-excl spins 4641946, OS waits 1530310
                '''
                pattern = '^RW-shared spins (\d+), rounds (\d+), OS waits (\d+); RW-excl spins (\d+), OS waits (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['spin_waits']+=int(m.group(1))
                    result['spin_rounds']+=int(m.group(2))
                    result['os_waits']+=int(m.group(3))

                ''' Example: Post 5.5.17 SHOW ENGINE INNODB STATUS syntax
                    RW-shared spins 604733, rounds 8107431, OS waits 241268
                '''
                pattern = '^RW-shared spins (\d+), rounds (\d+), OS waits (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['spin_waits']+=int(m.group(1))
                    result['spin_rounds']+=int(m.group(2))
                    result['os_waits']+=int(m.group(3))

                ''' Example: Post 5.5.17 SHOW ENGINE INNODB STATUS syntax
                    RW-excl spins 604733, rounds 8107431, OS waits 241268
                '''
                pattern = 'RW-excl spins (\d+), OS waits (\d+)$'
                m = re.search(pattern, line)
                if m:
                    result['spin_waits']+=int(m.group(1))
                    result['os_waits']+=int(m.group(2))

                ''' Example:
                    --Thread 907205 has waited at handler/ha_innodb.cc line 7156 for 1.00 seconds the semaphore:
                '''
                pattern = '^--Thread \d+ has waited at handler/ha_innodb.cc line \d+ for ([\.\d+]) seconds the semaphore'
                m = re.search(pattern, line)
                if m:
                    result['innodb_sem_waits']+=1
                    result['innodb_sem_wait_time_ms']+=int(m.group(1) * 1000)

            return result

        def get_status(self):
            result={}
            cursor = self.server.cnx.cursor()
            query="SHOW /*!50000 ENGINE*/ INNODB STATUS"
            cursor.execute(query)
            for (status_item) in cursor:
                data = self._parser(status_item[2].split('\n'))
            result['semaphores'] = self._semaphores_parser(data['SEMAPHORES'])
            result['transactions'] = self._transactions_parser(data['TRANSACTIONS'])
            result['file_io'] = self._file_io_parser(data['FILE I/O'])
            result['insert_buffer'] = self._insert_buffer_parser(data['INSERT BUFFER AND ADAPTIVE HASH INDEX'])
            result['log'] = self._log_parser(data['LOG'])
            result['row_ops'] = self._row_ops_parser(data['ROW OPERATIONS'])
            result['buffer_memory'] = self._buffer_memory_parser(data['BUFFER POOL AND MEMORY'])
            return result

        def filter_status(self, item):
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                value = item[1]
                if value in MYSQL_INNODB_MAPPING:
                    value = MYSQL_INNODB_MAPPING[value]
                return (key, value)
            return (False, False)

    ''' Galera class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/replication-cluster-multi-master/galera/galera-cluster-status-variables/
        wsrep_apply_oooe : decimal
        wsrep_apply_oool : decimal
        wsrep_cert_deps_distance : decimal
        wsrep_cluster_size : numeric
        wsrep_flow_control_paused : decimal
        wsrep_flow_control_recv : numeric
        wsrep_flow_control_sent : numeric
        wsrep_last_committed : numeric
        wsrep_local_bf_aborts : numeric
        wsrep_local_cert_failures : numeric
        wsrep_local_commits : numeric
        wsrep_local_index : numeric
        wsrep_local_recv_queue : numeric
        wsrep_local_recv_queue_avg : decimal
        wsrep_local_replays : numeric
        wsrep_local_send_queue : numeric
        wsrep_local_send_queue_avg : decimal
        wsrep_protocol_version : numeric
        wsrep_received : numeric
        wsrep_received_bytes : numeric
        wsrep_replicated : numeric
        wsrep_replicated_bytes : numeric
        wsrep_thread_count : numeric
    TODO:
        wsrep_cluster_status : enum [PRIMARY|NON_PRIMARY|DISCONNECTED]
        wsrep_connected : boolean [ON|OFF]
        wsrep_ready: boolean [ON|OFF]
    '''
    class Galera(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="wsrep_"

        def filter_status(self, item):
            if item[0].startswith(self.status_prefix) and \
               item[0].replace(self.status_prefix,'') in wsrep_status_keys:
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

        def is_enabled(self):
            cursor = self.server.cnx.cursor()
            cursor.execute("SHOW STATUS LIKE 'wsrep_ready'")
            for (item) in cursor:
                if item[0] == 'wsrep_ready' and item[1] == 'ON':
                    return True
            return False

    ''' Replication class (multi source ready) '''
    class Replication(object):

        def __init__(self, server):
            self.server = server

        def get_status(self):
            cursor = self.server.cnx.cursor()
            cursor.execute("SHOW ALL SLAVES STATUS")
            replication_list=[]
            for (replication_item) in cursor:
              replication_list.append(dict(zip(replication_keys,replication_item)))
            return replication_list

    ''' Cassandra class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/storage-engines/storage-engines-cassandra-storage-engine/cassandra-status-variables/
        Cassandra_multiget_keys_scanned : numeric
        Cassandra_multiget_reads : numeric
        Cassandra_multiget_rows_read : numeric
        Cassandra_row_insert_batches : numeric
        Cassandra_row_inserts : numeric
        Cassandra_timeout_exceptions : numeric
        Cassandra_unavailable_exceptions : numeric
    '''
    class Cassandra(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Cassandra_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' Aria class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/storage-engines/aria/aria-server-status-variables/
        Aria_pagecache_blocks_not_flushed : numeric
        Aria_pagecache_blocks_unused : numeric
        Aria_pagecache_blocks_used : numeric
        Aria_pagecache_read_requests : numeric
        Aria_pagecache_reads : numeric
        Aria_pagecache_write_requests : numeric
        Aria_pagecache_writes : numeric
        Aria_transaction_log_syncs : numeric
    '''
    class Aria(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Aria_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' TokuDB class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/storage-engines/tokudb/tokudb-status-variables/
        Tokudb_basements_decompressed_for_write : numeric
        Tokudb_basements_decompressed_prefetch : numeric
        Tokudb_basements_decompressed_prelocked_range : numeric
        Tokudb_basements_decompressed_target_query : numeric
        Tokudb_basements_fetched_for_write : numeric
        Tokudb_basements_fetched_for_write_bytes : numeric
        Tokudb_basements_fetched_for_write_seconds : decimal
        Tokudb_basements_fetched_prefetch : numeric
        Tokudb_basements_fetched_prefetch_bytes : numeric
        Tokudb_basements_fetched_prefetch_seconds : decimal
        Tokudb_basements_fetched_prelocked_range : numeric
        Tokudb_basements_fetched_prelocked_range_bytes : numeric
        Tokudb_basements_fetched_prelocked_range_seconds : decimal
        Tokudb_basements_fetched_target_query : numeric
        Tokudb_basements_fetched_target_query_bytes : numeric
        Tokudb_basements_fetched_target_query_seconds : decimal
        Tokudb_broadcase_messages_injected_at_root : numeric
        Tokudb_buffers_decompressed_for_write : numeric
        Tokudb_buffers_decompressed_prefetch : numeric
        Tokudb_buffers_decompressed_prelocked_range : numeric
        Tokudb_buffers_decompressed_target_query : numeric
        Tokudb_buffers_fetched_for_write : numeric
        Tokudb_buffers_fetched_for_write_bytes : numeric
        Tokudb_buffers_fetched_for_write_seconds : decimal
        Tokudb_buffers_fetched_prefetch : numeric
        Tokudb_buffers_fetched_prefetch_bytes : numeric
        Tokudb_buffers_fetched_prefetch_seconds : decimal
        Tokudb_buffers_fetched_prelocked_range : numeric
        Tokudb_buffers_fetched_prelocked_range_bytes : numeric
        Tokudb_buffers_fetched_prelocked_range_seconds : decimal
        Tokudb_buffers_fetched_target_query : numeric
        Tokudb_buffers_fetched_target_query_bytes : numeric
        Tokudb_buffers_fetched_target_query_seconds : decimal
        Tokudb_cachetable_cleaner_executions : decimal
        Tokudb_cachetable_cleaner_iterations : numeric
        Tokudb_cachetable_cleaner_period : decimal
        Tokudb_cachetable_evictions : numeric
        Tokudb_cachetable_long_wait_pressure_count : decimal
        Tokudb_cachetable_long_wait_pressure_time : decimal
        Tokudb_cachetable_miss : numeric
        Tokudb_cachetable_miss_time : decimal
        Tokudb_cachetable_prefetches : decimal
        Tokudb_cachetable_size_cachepressure : numeric
        Tokudb_cachetable_size_current : numeric
        Tokudb_cachetable_size_leaf : numeric
        Tokudb_cachetable_size_limit : numeric
        Tokudb_cachetable_size_nonleaf : numeric
        Tokudb_cachetable_size_rollback : numeric
        Tokudb_cachetable_size_writing : numeric
        Tokudb_cachetable_wait_pressure_count : decimal
        Tokudb_cachetable_wait_pressure_time : decimal
        Tokudb_checkpoint_begin_time : UNKNOWN
        Tokudb_checkpoint_failed : numeric
        Tokudb_checkpoint_last_began : datetime
        Tokudb_checkpoint_last_complete_began : datetime
        Tokudb_checkpoint_last_complete_ended : datetime
        Tokudb_checkpoint_long_begin_count : numeric
        Tokudb_checkpoint_long_begin_time : numeric
        Tokudb_checkpoint_period : decimal
        Tokudb_checkpoint_taken : numeric
        Tokudb_db_closes : numeric
        Tokudb_db_open_current : numeric
        Tokudb_db_open_max : numeric
        Tokudb_db_opens : numeric
        Tokudb_descriptor_set : numeric
        Tokudb_dictionary_broadcast_updates : numeric
        Tokudb_dictionary_updates : numeric
        Tokudb_filesystem_fsync_num : numeric
        Tokudb_filesystem_fsync_time : numeric
        Tokudb_filesystem_long_fsync_num : numeric
        Tokudb_filesystem_long_fsync_time : numeric
        Tokudb_filesystem_threads_blocked_by_full_disk : numeric
        Tokudb_leaf_compression_to_memory_seconds : decimal
        Tokudb_leaf_decompression_to_memory_seconds : decimal
        Tokudb_leaf_deserialization_to_memory_seconds : decimal
        Tokudb_leaf_node_compression_ratio : UNKNOWN
        Tokudb_leaf_node_full_evictions : numeric
        Tokudb_leaf_node_full_evictions_bytes : numeric
        Tokudb_leaf_node_partial_evictions : numeric
        Tokudb_leaf_node_partial_evictions_bytes : numeric
        Tokudb_leaf_nodes_created : numeric
        Tokudb_leaf_nodes_destroyed : numeric
        Tokudb_leaf_nodes_flushed_checkpoint : numeric
        Tokudb_leaf_nodes_flushed_checkpoint_bytes : numeric
        Tokudb_leaf_nodes_flushed_checkpoint_seconds : decimal
        Tokudb_leaf_nodes_flushed_checkpoint_uncompressed_bytes : numeric
        Tokudb_leaf_nodes_flushed_not_checkpoint : numeric
        Tokudb_leaf_nodes_flushed_not_checkpoint_bytes : numeric
        Tokudb_leaf_nodes_flushed_not_checkpoint_seconds : decimal
        Tokudb_leaf_nodes_flushed_not_checkpoint_uncompressed_bytes : numeric
        Tokudb_leaf_serialization_to_memory_seconds : decimal
        Tokudb_loader_num_created : numeric
        Tokudb_loader_num_current : numeric
        Tokudb_loader_num_max : numeric
        Tokudb_locktree_escalation_num : numeric
        Tokudb_locktree_escalation_seconds : decimal
        Tokudb_locktree_latest_post_escalation_memory_size : numeric
        Tokudb_locktree_long_wait_count : numeric
        Tokudb_locktree_long_wait_escalation_count : numeric
        Tokudb_locktree_long_wait_escalation_time : numeric
        Tokudb_locktree_long_wait_time : numeric
        Tokudb_locktree_memory_size : numeric
        Tokudb_locktree_memory_size_limit : numeric
        Tokudb_locktree_open_current : numeric
        Tokudb_locktree_pending_lock_requests : numeric
        Tokudb_locktree_sto_eligible_num : numeric
        Tokudb_locktree_sto_ended_num : numeric
        Tokudb_locktree_sto_ended_seconds : decimal
        Tokudb_locktree_timeout_count : numeric
        Tokudb_locktree_wait_count : numeric
        Tokudb_locktree_wait_escalation_count : numeric
        Tokudb_locktree_wait_escalation_time : numeric
        Tokudb_locktree_wait_time : numeric
        Tokudb_logger_wait_long : UNKNOWN
        Tokudb_logger_writes : numeric
        Tokudb_logger_writes_bytes : numeric
        Tokudb_logger_writes_seconds : decimal
        Tokudb_logger_writes_uncompressed_bytes : numeric
        Tokudb_mem_estimated_maximum_memory_footprint : UNKNOWN
        Tokudb_messages_flushed_from_h1_to_leaves_bytes : numeric
        Tokudb_messages_ignored_by_leaf_due_to_msn : numeric
        Tokudb_messages_in_trees_estimate_bytes : numeric
        Tokudb_messages_injected_at_root : numeric
        Tokudb_messages_injected_at_root_bytes : numeric
        Tokudb_nonleaf_compression_to_memory_seconds : decimal
        Tokudb_nonleaf_decompression_to_memory_seconds : decimal
        Tokudb_nonleaf_deserialization_to_memory_seconds : decimal
        Tokudb_nonleaf_node_compression_ratio : decimal
        Tokudb_nonleaf_node_full_evictions : numeric
        Tokudb_nonleaf_node_full_evictions_bytes : numeric
        Tokudb_nonleaf_node_partial_evictions : numeric
        Tokudb_nonleaf_node_partial_evictions_bytes : numeric
        Tokudb_nonleaf_nodes_created : numeric
        Tokudb_nonleaf_nodes_destroyed : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_checkpoint : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_checkpoint_bytes : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_checkpoint_seconds : decimal
        Tokudb_nonleaf_nodes_flushed_to_disk_checkpoint_uncompressed_bytes : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_not_checkpoint : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_not_checkpoint_bytes : numeric
        Tokudb_nonleaf_nodes_flushed_to_disk_not_checkpoint_seconds : decimal
        Tokudb_nonleaf_nodes_flushed_to_disk_not_checkpoint_uncompressed_bytes : numeric
        Tokudb_nonleaf_serialization_to_memory_seconds : decimal
        Tokudb_overall_node_compression_ratio : decimal
        Tokudb_pivots_fetched_for_query : numeric
        Tokudb_pivots_fetched_for_query_bytes : numeric
        Tokudb_pivots_fetched_for_query_seconds : decimal
        Tokudb_pivots_fetched_for_prefetch : numeric
        Tokudb_pivots_fetched_for_prefetch_bytes : numeric
        Tokudb_pivots_fetched_for_prefetch_seconds : decimal
        Tokudb_pivots_fetched_for_write : numeric
        Tokudb_pivots_fetched_for_write_bytes : numeric
        Tokudb_pivots_fetched_for_write_seconds : decimal
        Tokudb_promotion_h1_roots_injected_into : numeric
        Tokudb_promotion_injections_at_depth_0 : numeric
        Tokudb_promotion_injections_at_depth_1 : numeric
        Tokudb_promotion_injections_at_depth_2 : numeric
        Tokudb_promotion_injections_at_depth_3 : numeric
        Tokudb_promotion_injections_lower_than_depth_3 : numeric
        Tokudb_promotion_leaf_roots_injected_into : numeric
        Tokudb_promotion_roots_split : numeric
        Tokudb_promotion_stopped_after_locking_child : numeric
        Tokudb_promotion_stopped_at_height_1 : numeric
        Tokudb_promotion_stopped_child_locked_or_not_in_memory : numeric
        Tokudb_promotion_stopped_child_not_fully_in_memory : numeric
        Tokudb_promotion_stopped_nonempty_buffer : numeric
        Tokudb_txn_aborts : numeric
        Tokudb_txn_begin : numeric
        Tokudb_txn_begin_read_only : numeric
        Tokudb_txn_commits : numeric
    '''
    class Tokudb(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Tokudb_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' Sphinx class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/optimization-and-tuning/system-variables/sphinx-status-variables/
        Sphinx_error : numeric
        Sphinx_time : numeric
        Sphinx_total : numeric
        Sphinx_total_found : numeric
        Sphinx_word_count : numeric
        Sphinx_words : numeric
    '''
    class Sphinx(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Sphinx_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' Server_audit class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/mariadb-plugins/server_audit-mariadb-audit-plugin/server_audit-status-variables/
        Server_audit_active : boolean [ON|OFF]
        Server_audit_writes_failed : numeric
    '''
    class ServerAudit(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Server_audit_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' Spider class
    Ref: https://mariadb.com/kb/en/mariadb/documentation/optimization-and-tuning/system-variables/spider-server-status-variables/
        Spider_direct_aggregate : numeric
        Spider_direct_order_limit : numeric
        Spider_mon_table_cache_version : numeric
        Spider_mon_table_cache_version_req : numeric
    '''
    class Spider(object):

        def __init__(self, server):
            self.server = server
            self.status_prefix="Spider_"

        def filter_status(self, item):
            return (False, False)
            ''' NOT IMPLEMENTED ON ZABBIX SIDE '''
            if item[0].startswith(self.status_prefix):
                key=item[0].replace(self.status_prefix,'')
                return (key, item[1])
            return (False, False)

    ''' MysqlServer class '''
    def __init__(self, user_name='guest', password='guest',
                 host_name='', port=3306, database='mysql'):
        self.config = {
          'user': user_name,
          'password': password,
          'host': host_name,
          'database': database
        }
        ''' Initialize connection'''
        self.cnx = mysql.connector.connect(**self.config)
        ''' Initialize sub-classes '''
        self.replication = self.Replication(self)
        self.plugins = {
            'galera' : self.Galera(self),
            'innodb' : self.Innodb(self),
            'aria' : self.Aria(self),
            'cassandra' : self.Cassandra(self),
            'tokudb' : self.Tokudb(self),
            'sphinx' : self.Sphinx(self),
            'serveraudit' : self.ServerAudit(self),
            'spider' : self.Spider(self)
        }
        self.galera = self.Galera(self)
        self.innodb = self.Innodb(self)
        self.aria = self.Aria(self)
        self.cassandra = self.Cassandra(self)
        self.tokudb = self.Tokudb(self)
        self.sphinx = self.Sphinx(self)
        self.serveraudit = self.ServerAudit(self)
        self.spider = self.Spider(self)
        ''' Initialize variables '''
        self.repl_discovery_key = 'mysql.server.replication.discovery'
        self.galera_discovery_key = 'mysql.server.plugins[galera,discovery]'
        self.innodb_discovery_key = 'mysql.server.plugins[innodb,discovery]'
        self.aria_discovery_key = 'mysql.server.plugins[aria,discovery]'
        self.cassandra_discovery_key = 'mysql.server.plugins[cassandra,discovery]'
        self.tokudb_discovery_key = 'mysql.server.plugins[tokudb,discovery]'
        self.sphinx_discovery_key = 'mysql.server.plugins[sphinx,discovery]'
        self.serveraudit_discovery_key = 'mysql.server.plugins[serveraudit,discovery]'
        self.spider_discovery_key = 'mysql.server.plugins[spider,discovery]'

    def __del__(self):
        self.cnx.close()

    def _get_engines(self):
        covered_engines = [
            'innodb',
            'aria',
            'cassandra',
            'tokudb',
            'sphinx',
            'spider'
        ]
        enabled_engines = []
        cursor = self.cnx.cursor()
        cursor.execute("SHOW ENGINES")
        for engine_item in cursor:
            if engine_item[0].lower() in covered_engines:
                enabled_engines.append(engine_item[0].lower())

        return enabled_engines

    def filter_status(self,item):
        key=item[0].lower()
        if key in status_bl:
            return(False, False)
        return (key, item[1])

    ''' Global function to get 'show status' items '''
    def get_status(self):
        global_status = {}
        cursor = self.cnx.cursor()
        cursor.execute("SHOW GLOBAL STATUS")
        for status_item in cursor:
            ''' Filter Global status '''
            (key, value) = self.filter_status(status_item)
            if key and value:
                global_status[key] = value

            ''' Find wether current item belongs to a plugin '''
            for plugin_name in self.plugins:
                if plugin_name not in global_status:
                    global_status[plugin_name] = {}
                plugin = self.plugins[plugin_name]
                prefix = plugin.status_prefix
                if status_item[0].startswith(prefix):
                    ''' Filter Innodb results '''
                    (key, value) = plugin.filter_status(status_item)
                    if key and value:
                        global_status[plugin_name][key] = value
                    ''' unset global status key if belong to plugin '''
                    del global_status[status_item[0].lower()]

        return global_status

    ''' Global function to get LLD data '''
    def get_discovery(self):
        data = {
            self.repl_discovery_key:[],
        }
        ''' Perform storage engines LLD ops '''
        engines_list = self._get_engines()
        for engine in engines_list:
            data['mysql.server.plugins['+engine+',discovery]'] = [{'{#MYSQLACTIVEPLUGIN}': engine}]

        ''' Galera is not a storage engine '''
        if self.galera.is_enabled():
            data['mysql.server.plugins[galera,discovery]'] = [{'{#MYSQLACTIVEPLUGIN}': 'galera'}]

        ''' Perform replication LLD ops '''
        for replication in self.replication.get_status():
            replication_name=replication['connection_name']
            if(replication['connection_name']==""):
                replication_name=replication['master_host']
            data[self.repl_discovery_key].append({'{#MYSQLREPNAME}': replication_name})
        self.cnx.close()
        return data

    ''' Global function to get items data '''
    def get_metrics(self):
        data = {}
        ''' Check Replication status
            Compatible with multi-source replication '''
        replication_list=self.replication.get_status()
        zbx_key = "mysql.server.replication.sources"
        data[zbx_key] = len(replication_list)
        for replication in replication_list:
          ''' For single source replication, connection name is not set
              In that case, we use master_host value as connection name '''
          replication_name=replication['connection_name']
          if(replication['connection_name']==""):
            replication_name=replication['master_host']

          ''' report wether master_log_file and relay_master_log_file differ '''
          master_files_diff=0
          if(replication['master_log_file'] != replication['relay_master_log_file']):
            master_files_diff = 1
          zbx_key = "mysql.server.replication[{0},master_files_diff]"
          zbx_key = zbx_key.format(replication_name)
          data[zbx_key] = master_files_diff

          ''' report boolean replication status '''
          for item in ['slave_io_running','slave_sql_running','using_gtid']:
            zbx_key = "mysql.server.replication[{0},{1}]"
            zbx_key = zbx_key.format(replication_name, item)
            data[zbx_key] = MYSQL_REPLICATION_MAPPING[replication[item]]

          ''' report integer replication status '''
          for item in [ 'last_errno', 'last_io_errno', 'last_sql_errno',
                        'read_master_log_pos','exec_master_log_pos',
                        'seconds_behind_master']:
            zbx_key = "mysql.server.replication[{0},{1}]"
            zbx_key = zbx_key.format(replication_name, item)
            data[zbx_key] = replication[item]

        ''' Check Innodb status '''
        '''
        data['mysql.server.plugins[innodb,enabled]'] = 0
        innodb_status=self.innodb.get_status()
        if len(innodb_status):
            data['mysql.server.plugins[innodb2,enabled]'] = 1
            for key in innodb_status:
                for subkey in innodb_status[key]:
                    zbx_key="mysql.server.plugins[innodb2,{0},{1}]"
                    zbx_key=zbx_key.format(key,subkey)
                    data[zbx_key]=innodb_status[key][subkey]
        '''

        global_status = self.get_status()
        for plugin in global_status:
            if type(global_status[plugin]) is dict:
                ''' Plugins status informations '''
                plugin_key = "mysql.server.plugins[{0},enabled]"
                plugin_key = plugin_key.format(plugin)
                data[plugin_key] = 0
                if len(global_status[plugin]):
                    data[plugin_key] = 1
                    for item in global_status[plugin]:
                        zbx_key="mysql.server.plugins[{0},{1}]"
                        zbx_key=zbx_key.format(plugin, item)
                        data[zbx_key]=global_status[plugin][item]
            else:
                ''' Global status informations '''
                zbx_key="mysql.server.{0}"
                zbx_key=zbx_key.format(plugin)
                data[zbx_key]=global_status[plugin]

        data["mysql.server.zbx_version"] = __version__
        self.cnx.close()
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
        obj = MysqlServer(user_name=options.username,
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
