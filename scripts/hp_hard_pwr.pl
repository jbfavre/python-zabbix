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
my $rank  = 0;
my @powerinfos;
my %thash;

sub getInfo {

  open(HPLOG, "/sbin/hpasmcli -s 'SHOW POWERSUPPLY' |") || die "Could not run hpasmcli\n";

  while (<HPLOG>) {

    if (/Power supply #(\d+)/) {

      if (defined($thash{'slot'})) {
        push @powerinfos, { %thash };
      }

      $rank = $1;
      $thash{'slot'} = $rank;
    }
    if ( my ($key, $value) = /\s+(Present|Redundant|Hotplug|Condition|Power)\s*:\s+(\w+)\s?\w?/) {
      $thash{$key} = $value;
    }
  }
  if (defined($thash{'slot'})) {
    push @powerinfos, { %thash };
  }
  close(HPLOG);

}

getInfo();

if ( $ARGV[0] and $ARGV[0] eq "discovery") {
  # Display discovery informations

  print "- hp.hardware.power.discovery {\"data\":[";

  foreach my $powerinfo ( @powerinfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#POWERID}\":\"power".$powerinfo->{slot}."\",";
    print "\"{#POWERSLOT}\":\"".$powerinfo->{slot}."\",";
    print "\"{#POWERHOTPLUG}\":\"".$powerinfo->{Hotplug}."\",";
    print "\"{#POWERREDUNDANT}\":\"".$powerinfo->{Redundant}."\",";
    print "\"{#POWERPRESENT}\":\"".$powerinfo->{Present}."\"}";
  }
  print "]}\n";

}else{
  # Display trappers metrics

  foreach my $powerinfo ( @powerinfos ) {
    print "- hp.hardware.power[$powerinfo->{slot},status] $powerinfo->{Condition}\n";
    print "- hp.hardware.power[$powerinfo->{slot},watts] $powerinfo->{Power}\n";
  }

}
