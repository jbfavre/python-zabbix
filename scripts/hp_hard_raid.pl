#!/usr/bin/env perl
#
# hpacu - Munin plugin for HP Array Controllers
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
my $tmp;

my @controllerinfos;
my %controllerthash;

my @logicaldriveinfos;
my %logicaldrivethash;

my @physicaldriveinfos;
my %physicaldrivethash;

sub getInfo {

  open(HPACU, "/usr/sbin/hpacucli controller all show |") || die "Could not run hpacucli\n";

  while (<HPACU>) {

    # Detect Controller slot
    next if /^\s*$/;
    if (/Smart Array\s+([^\s]+) in Slot (\d+)/) {
      if (defined($controllerthash{'slot'})) {
        push @controllerinfos, { %controllerthash };
      }
      $rank = $2;
      $controllerthash{'slot'} = $rank;
      $controllerthash{'model_name'} = $1;
    }

    # Analyze controller details
    open(HPACUCTRL, "/usr/sbin/hpacucli controller slot=$rank show |") || die "Could not run hpacucli\n";
    while (<HPACUCTRL>) {

      if ( my ( $key, $value ) = /^\s+(Serial Number|Cache Serial Number|Controller Status|Hardware Revision|Firmware Version|Cache Status|Battery\/Capacitor Status|Total Cache Size|Total Cache Memory Available):\s+([^\s]+)/) {
        $key = $1;
        $key =~ s/[\s\/]+/_/ig;
        $controllerthash{lc $key} = $value;
      }
      if ( my ( $temp, $value, $thres ) = /^\s+(Controller Temperature|Cache Module Temperature|Capacitor Temperature)\s+\(\w\):\s+([^\s]+)/) {
        $temp =~ s/\s+/_/g;
        $controllerthash{lc $temp} = $value;
      }
      if ( my ( $read, $write ) = /^\s+Cache Ratio:\s+([^\s]+)%\s+Read\s+\/\s+([^\s]+)%\s+Write/) {
        $controllerthash{'cache_read_ratio'} = $read;
        $controllerthash{'cache_write_ratio'} = $write;
      }
    }
    close(HPACUCTRL);

    # For current controller, check logical drives
    open(HPACULD, "/usr/sbin/hpacucli controller slot=$rank logicaldrive all show status |") || die "Could not run hpacucli\n";
    while (<HPACULD>) {
      if (/\s+logicaldrive (\d)+ \(.+, RAID (\d)+\):\s+(\w+)/) {
        push @logicaldriveinfos, {
          'id'             => $1,
          'controllerslot' => $rank,
          'raid_type'      => $2,
          'status'         => $3
        }
      }
    }
    close(HPACULD);

    # For current controller, check physical drives
    open(HPACUPD, "/usr/sbin/hpacucli controller slot=$rank physicaldrive all show status |") || die "Could not run hpacucli\n";
    while (<HPACUPD>) {
      if (/physicaldrive (.+) \(port (.+):box (\d+):bay (\d+), (\d+) GB\):\s+(\w+)/) {
        push @physicaldriveinfos, {
          'id'            => $1,
          'controllerslot' => $rank,
          'port'          => $2,
          'box'           => $3,
          'bay'           => $4,
          'capacity'      => $5,
          'status'        => $6
        }
      }
    }

  }
  if (defined($controllerthash{'slot'})) {
    push @controllerinfos, { %controllerthash };
  }
  close(HPACU);
}

getInfo();

if ( $ARGV[0] and $ARGV[0] eq "discovery") {
  # Display discovery informations

  print "- hp.hardware.raid.controller.discovery {\"data\":[";

  foreach my $controllerinfo ( @controllerinfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#CONTROLLERID}\":\"controller".$controllerinfo->{slot}."\",";
    print "\"{#CONTROLLERSLOT}\":\"".$controllerinfo->{slot}."\",";
    print "\"{#CONTROLLERMODEL}\":\"".$controllerinfo->{model_name}."\",";
    print "\"{#CONTROLLERSERIAL}\":\"".$controllerinfo->{serial_number}."\",";
    print "\"{#CONTROLLERFIRMWARE}\":\"".$controllerinfo->{firmware_version}."\",";
    print "\"{#CONTROLLERHARDWARE}\":\"".$controllerinfo->{hardware_revision}."\",";
    print "\"{#CONTROLLERCACHESERIAL}\":\"".$controllerinfo->{cache_serial_number}."\",";
    print "\"{#CONTROLLERCACHEMEMORY}\":\"".$controllerinfo->{total_cache_size}."\"}";

  }
  print "]}\n";

  $first = 1;
  print "- hp.hardware.raid.logicaldrive.discovery {\"data\":[";

  foreach my $logicaldriveinfo ( @logicaldriveinfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#LOGICALDRIVEID}\":\"logicaldrive".$logicaldriveinfo->{id}."\",";
    print "\"{#LOGICALDRIVESLOT}\":\"".$logicaldriveinfo->{id}."\",";
    print "\"{#CONTROLLERSLOT}\":\"".$logicaldriveinfo->{controllerslot}."\",";
    print "\"{#LOGICALDRIVERAID}\":\"".$logicaldriveinfo->{raid_type}."\"}";

  }
  print "]}\n";

  $first = 1;
  print "- hp.hardware.raid.physicaldrive.discovery {\"data\":[";

  foreach my $physicaldriveinfo ( @physicaldriveinfos ) {
    print "," if not $first;
    $first = 0;

    print "{\"{#PHYSICALDRIVEID}\":\"physicaldrive".$physicaldriveinfo->{id}."\",";
    print "\"{#PHYSICALDRIVESLOT}\":\"".$physicaldriveinfo->{id}."\",";
    print "\"{#CONTROLLERSLOT}\":\"".$physicaldriveinfo->{controllerslot}."\",";
    print "\"{#PHYSICALDRIVEPORT}\":\"".$physicaldriveinfo->{port}."\",";
    print "\"{#PHYSICALDRIVEBOX}\":\"".$physicaldriveinfo->{box}."\",";
    print "\"{#PHYSICALDRIVEBAY}\":\"".$physicaldriveinfo->{bay}."\",";
    print "\"{#PHYSICALDRIVECAPACITY}\":\"".$physicaldriveinfo->{capacity}."\"}";

  }
  print "]}\n";

}else{
  # Display trappers metrics

  foreach my $controllerinfo ( @controllerinfos ) {
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},controller_status] $controllerinfo->{'controller_status'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},controller_temperature] $controllerinfo->{'controller_temperature'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},cache_status] $controllerinfo->{'cache_status'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},cache_module_temperature] $controllerinfo->{'cache_module_temperature'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},cache_read_ratio] $controllerinfo->{'cache_read_ratio'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},cache_write_ratio] $controllerinfo->{'cache_write_ratio'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},total_cache_memory_available] $controllerinfo->{'total_cache_memory_available'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},battery_capacitor_status] $controllerinfo->{'battery_capacitor_status'}\n";
    print "- hp.hardware.raid.controller[$controllerinfo->{slot},capacitor_temperature] $controllerinfo->{'capacitor_temperature'}\n";
  }

  foreach my $logicaldriveinfo ( @logicaldriveinfos ) {
    print "- hp.hardware.raid.logicaldrive[$logicaldriveinfo->{controllerslot}:$logicaldriveinfo->{id},status] $logicaldriveinfo->{status}\n";
  }

  foreach my $physicaldriveinfo ( @physicaldriveinfos ) {
    print "- hp.hardware.raid.physicaldrive[".$physicaldriveinfo->{id}.",status] $physicaldriveinfo->{status}\n";
  }


}

