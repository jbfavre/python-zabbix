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
my @tempinfos;

sub getInfo {
  open(HPLOG, "/sbin/hplog -t |") || die "Could not run hplog\n";
  while (<HPLOG>) {
    next if /^\s*$/;
    next if /^\s*ID/;
    if (/^\s*(\d+)\s*Basic Sensor\s+(Ambient|CPU \(\d+\)|Memory Board|System Board|Pwr\. Supply Bay|Processor Zone|I\/O Zone|Chassis)\s+(\S+)\s+\d+F\/\s*(\d+)C\s+\d+F\/\s*(\d+)C/) {
      push @tempinfos, {
        'id'        => $1,
        'location'  => $2,
        'status'    => $3,
        'current'   => $4,
        'threshold' => $5
      }
    }
  }
  close(HPLOG);
}

getInfo();

if ( $ARGV[0] and $ARGV[0] eq "discovery") {
  # Display discovery informations

  print "- hp.hardware.temp.discovery {\"data\":[";

  foreach my $tempinfo ( @tempinfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#TEMPID}\":\"temp".$tempinfo->{id}."\",";
    print "\"{#TEMPSLOT}\":\"".$tempinfo->{id}."\",";
    print "\"{#TEMPLOCATION}\":\"".$tempinfo->{location}."\",";
    print "\"{#TEMPTHRES}\":\"".$tempinfo->{threshold}."\"}";
  }
  print "]}";

}else{
  # Display trappers metrics

  foreach my $tempinfo ( @tempinfos ) {
    #print "- hp.hardware.temp[$tempinfo->{id},status] $tempinfo->{status}\n";
    print "- hp.hardware.temp[$tempinfo->{id},current] $tempinfo->{current}\n";
  }

}
