#!/usr/bin/perl

# check_areca_vols 
#   Nagios/Icinga plugin to check the status of volumes on an
#   ARECA Raid controller under Linux.  Requires cli32/cli64
#   to be available -- see the $CLI variable at the top of
#   the script
#
#
# Written by Joseph Dickson <joseph.dickson@ajboggs.com>
# for AJ BOGGS & CO <http://www.ajboggs.com>
#
# Copyright 2011 by AJ BOGGS & CO
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


# where we can expect to find the cli32/cli64 program.  This example
# assumes that you are granting access to run the cli64 program via
$CLI = '/usr/local/bin/cli64';
my $first = 1;
my @volinfos;

eval {
    my $exit_code = 0;
    my $primary_info = "";

    $numvols = areca_count_volumes();
    if ($numvols == 0) { die "no volumes available to check" }

    for (my $volid = 1; $volid <= $numvols; $volid++) {
        $vinfo = areca_get_vol_info($volid); 
        
    }

    if ( $ARGV[0] and $ARGV[0] eq "discovery") {
      # Display discovery informations
      print "- areca.volume.discovery {\"data\":[";
      foreach my $volinfo ( @volinfos ) {
        print "," if not $first;
        $first = 0;

        $volinfo->{name} =~ s/^\s+|\s+$//g;
        $volinfo->{raidset} =~ s/^\s+|\s+$//g;
        print "{\"{#VOLNAME}\":\"".$volinfo->{name}."\",";
        print "\"{#VOLRAIDSET}\":\"".$volinfo->{raidset}."\",";
        print "\"{#VOLSIZE}\":\"".$volinfo->{size}."\",";
        print "\"{#VOLLUN}\":\"".$volinfo->{lun}."\",";
        print "\"{#VOLRAIDLEVEL}\":\"".$volinfo->{raidlevel}."\",";
        print "\"{#VOLNUMDISKS}\":\"".$volinfo->{numdisks}."\"}";
      }
      print "]}\n";

    }else{
      # Display trappers metrics

      foreach my $volinfo ( @volinfos ) {
        # Uses zabbix mapping "Service state"
        # Service up = 1
        # Service down = 0
        my $state_code = 1;
        if ($volinfo->{state} ne "Normal") {
          $state_code = 0;
        }
        $volinfo->{name} =~ s/^\s+|\s+$//g;
        print "- areca.volume[$volinfo->{name},state] $state_code\n";
      }

    }

    exit($exit_code);
};
if (my $excep = $@) {
    exit(3);
}

# shouldn't make it here, but if we do, let's exit non-zero
exit(3);


# function:  areca_get_vol_info
# arguments:  volid
#
# returns a hashref full of volume info about the specified volume id..
# should be executed within an eval, as it can throw an exception
#
sub areca_get_vol_info {
    my $volid = shift;

    my $vinfo = { };
    $$vinfo{id} = $volid;

    open(CLI_PIPE, "$CLI vsf info vol=$volid|") || die "couldn't open pipe";

    while (<CLI_PIPE>) {
        if (/^Volume Set Name\s+: (.+)$/) { $$vinfo{name} = $1; }
        if (/^Raid Set Name\s+: (.+)$/) { $$vinfo{raidset} = $1; }
        if (/^Volume Capacity\s+: (.+)$/) { $$vinfo{size} = $1; }
        if (/^SCSI Ch\/Id\/Lun\s+: (.+)$/) { $$vinfo{lun} = $1; }
        if (/^Raid Level\s+: (.+)$/) { $$vinfo{raidlevel} = $1; }
        if (/^Member Disks\s+: (.+)$/) { $$vinfo{numdisks} = $1; }
        if (/^Volume State\s+: (.+)$/) { $$vinfo{state} = $1; }
    }

    close(CLI_PIPE);
    push @volinfos, $vinfo;

    return $vinfo;
}

# function:  areca_count_volumes
# arguments:  none 
#
# returns the number of volumes counted 
#  
# this routine does a vsf info command and counts the number of lines
# in between the ==== lines to determine the number of volumes on
# a controller.  Can throw a text exception.
sub areca_count_volumes {
	open(CLI_PIPE, "$CLI vsf info|") || die "couldn't open pipe";
	my $counting = 0;
	my $count = 0;
	while (<CLI_PIPE>) {
		if (/^========/) {
		    if ($counting) {
                $counting = 0;
            } else {
                $counting = 1;
            }
        } else {
            $count++ if $counting;
        }
    }
    
    close(CLI_PIPE);
    return $count;
}
