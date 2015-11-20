#!/usr/bin/env python
''' Copyright (c) 2015 Jean Baptiste Favre.
    Script for monitoring disks stats from Zabbix.
    Only add valid mounted point to monitoring
'''

import os
import re
import sys
import socket
import protobix

class DiskStats(protobix.SampleProbe):

    __version__ = '0.0.9'
    discovery_key = 'diskstats.discovery'
    authorized_fs_type = '^(btrfs|ext2|ext3|ext4|jfs|reiser|xfs|ffs|ufs|jfs|jfs2|vxfs|hfs|ntfs|fat32)$'

    def _parse_args(self):
        parser = super( DiskStats, self)._parse_args()
        (options, args) = parser.parse_args()
        return (options, args)

    def _diskstats_parse(self, dev=None):
        file_path = '/proc/diskstats'
        result = {}

        # ref: http://lxr.osuosl.org/source/Documentation/iostats.txt
        columns_disk = ['m', 'mm', 'dev', 'read_count', 'rd_mrg', 'rd_sectors',
                        'ms_reading', 'writes_count', 'wr_mrg', 'wr_sectors',
                        'ms_writing', 'cur_ios', 'ms_doing_io', 'ms_weighted']
        columns_partition = ['m', 'mm', 'dev', 'reads', 'rd_sectors', 'writes', 'wr_sectors']

        lines = open(file_path, 'r').readlines()
        for line in lines:
            if line == '': continue
            split = line.split()
            if len(split) == len(columns_disk):
                columns = columns_disk
            elif len(split) == len(columns_partition):
                columns = columns_partition
            else:
                # No match
                continue

            data = dict(zip(columns, split))
            if dev != None and dev != data['dev']:
                continue
            for key in data:
                if key != 'dev':
                    data[key] = int(data[key])
            result[data['dev']] = data
        return result

    def _init_probe(self):
        self.hostname = socket.getfqdn()

    def _get_mount_points(self):
        data = []
        mounted_file = '/proc/mounts'
        p = re.compile(self.authorized_fs_type)
        lines = open(mounted_file, 'r').readlines()
        for line in lines:
            if line == '': continue
            split = line.split()
            device_full_name = split[0]
            mount_point = split[1]
            fs_type = split[2]
            if device_full_name[0] == '/' and p.match(fs_type):
              # Mounted disk device
              real_device_name = device_full_name
              if os.path.islink(real_device_name):
                real_device_name = os.path.realpath(device_full_name)
              short_real_device_name = os.path.basename(real_device_name)
              element = [ short_real_device_name, device_full_name , mount_point , fs_type]
              data.append(element)
        return data 

    def _get_metrics(self):
        data = {}
        for disk in self._get_mount_points():
            diskstat = self._diskstats_parse(disk[0])
            if diskstat != {}:
                for key in diskstat[disk[0]]:
                    zbx_key = "diskstats[{0},{1}]"
                    zbx_key = zbx_key.format(disk[2], key)
                    data[zbx_key] = diskstat[disk[0]][key]
        data["diskstats.zbx_version"] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = DiskStats().run()
    print((ret))
    sys.exit(ret)
