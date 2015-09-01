#!/usr/bin/env python
''' Copyright (c) 2015 Jean Baptiste Favre.
    Script for monitoring disks stats from Zabbix.
'''

import sys
import protobix

class DiskStats(protobix.SampleProbe):

    __version__ = '0.0.9'
    discovery_key = 'diskstats.discovery'

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
        if self.options.host == 'localhost':
            self.options.host = socket.getfqdn()
        self.hostname = self.options.host

    def _get_discovery(self):
        data = {self.discovery_key:[]}
        for disk in ['sda', 'sdb', 'sdc', 'sdd']:
            element = { '{#DISKNAME}': disk }
            data[self.discovery_key].append(element)
        return { self.hostname: data }

    def _get_metrics(self):
        data = {}
        for disk in ['sda', 'sdb', 'sdc', 'sdd']:
            diskstat = self._diskstats_parse(disk)
            if diskstat != {}:
                for key in diskstat[disk]:
                    zbx_key = "diskstats[{0},{1}]"
                    zbx_key = zbx_key.format(disk, key)
                    data[zbx_key] = diskstat[disk][key]
        data["diskstats.zbx_version"] = self.__version__
        return { self.hostname: data }

if __name__ == '__main__':
    ret = DiskStats().run()
    print((ret))
    sys.exit(ret)