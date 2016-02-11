#!/usr/bin/env perl
#
# hpfan - Munin plugin for HP server fans
#
# Copyright (C) 2010 Magnus Hagander
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

use strict;
use warnings;

my $first = 1;
my @faninfos;

sub getInfo {

  open(HPLOG, "/sbin/hpasmcli -s 'SHOW FANS' |") || die "Could not run hplog\n";

  while (<HPLOG>) {

    next if /^\s*$/;
    next if /^\s*Fan/;

    if (/#(\d+)\s+(\w+)\s+(Yes)\s+(\w+)\s+(\d+)%\s+(Yes|No|N\/A)\s+(\d+|N\/A)\s+(Yes|No)/) {
      push @faninfos, {
        'slot' => $1,
        'location' => $2,
        'present' => $3,
        'speed' => $4,
        'speed_percent' => $5,
        'redundant' => $6,
        'partner' => $7,
        'hotplug' => $8
      };

    }

  }

  close(HPLOG);
}

getInfo();

if ( $ARGV[0] and $ARGV[0] eq "discovery") {
  # Display discovery informations

  print "- hp.hardware.fan.discovery {\"data\":[";

  foreach my $faninfo ( @faninfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#FANID}\":\"fan".$faninfo->{slot}."\",";
    print "\"{#FANSLOT}\":\"".$faninfo->{slot}."\",";
    print "\"{#FANLOCATION}\":\"".$faninfo->{location}."\",";
    print "\"{#FANHOTPLUG}\":\"".$faninfo->{hotplug}."\",";
    print "\"{#FANREDUNDANT}\":\"".$faninfo->{redundant}."\",";
    print "\"{#FANPRESENT}\":\"".$faninfo->{present}."\"}";
  }
  print "]}\n";

}else{
  # Display trappers metrics

  foreach my $faninfo ( @faninfos ) {
    print "- hp.hardware.fan[$faninfo->{slot},speed_percent] $faninfo->{speed_percent}\n";
  }

}
