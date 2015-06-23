#! /usr/bin/perl -w
######################################################################
# Name: check_hpIML
# By: Copyright (C) 2010 Remi Paulmier <remi@comuto.com>
# Credits to: andreiw
######################################################################
# Licence: GPL 2.0
######################################################################
######################################################################
# Description:
#
# A Nagios plugin that checks HP Health events via the hpasmcli tool.
# hpasmcli can be found in the hp-health package from HP. (previously 
# named hpasm).
#
# hpasmcli needs administrator rights.
# add this line to /etc/sudoers
#
# nagios      ALL=NOPASSWD: /usr/sbin/hpasmcli
######################################################################


######################################################################
# Each event in the IML Viewer has one of the following statuses to 
# identify the severity of the event:
#    
#    Informational - General information about a
#    system event.
#    
#    Repaired - An indication that the entry has been
#    repaired.
#    
#    Caution - An indication that a non-fatal error
#    condition has occurred.
#    
#    Critical - A component of the system has failed.
######################################################################


use strict;
use Getopt::Long;


$ENV{PATH} = "/bin:/sbin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin";

my %exit_codes = (
    'OK' => 0,
    'WARNING' => 1,
    'CRITICAL' => 2,
    'UNKNOWN' => 3
    );

my $progname = $0;

sub print_usage() 
{
    print "
Usage: $progname [-h|--help] [-V|--version] [-v #|--verbose=#]

	-h|--help		: this help
	-V|--version		: print version
	-v #|--verbose=#	: set verbosity, from 0 to 3, default is 0

";
}

my ($opt_help, $opt_verbose, $opt_version);

# defaults
$opt_verbose = 0;

Getopt::Long::Configure('gnu_getopt');
GetOptions(
    'h' => \$opt_help, 'help' => \$opt_help,
    'V' => \$opt_version, 'version' => \$opt_version,
    'v=i' => \$opt_verbose, 'verbose=i' => \$opt_verbose
    );

if (defined($opt_help)) {
    &print_usage;
    exit $exit_codes{UNKNOWN};
}

my %iml_lcodes = (
    'NONE' => 0,
    'INFO' => 1,
    'REPAIRED' => 2,
    'CAUTION' => 3,
    'CRITICAL' => 4
    );

my %iml_worst_event = (
    'level' => 'NONE',
    'desc' => "",
    'date' => "",
    'hour' => ""
    );

my ($edate, $ehour);

my $hpasmcli = "hpasmcli -s 'show iml'|";
open (HPASM, $hpasmcli);

LINE: while (<HPASM>) {
    
    chomp;
    
    print "DD: read: $_\n" if $opt_verbose ge 3;
    
    next LINE if /^[[:space:]]*$/;
    
    if (/^Event:/) {
	(undef, undef, undef, $edate, $ehour) = split(/ /, $_);
	
    } elsif (my ($elevel, $edesc) = /^(INFO|EPAIRED|CAUTION|CRITICAL):(.*)$/) {
	print "DD: $elevel event: $edesc\n" if $opt_verbose ge 2;
 	if ($iml_lcodes{$iml_worst_event{level}} le $iml_lcodes{$elevel}) {
 	    $iml_worst_event{date} = $edate;
	    $iml_worst_event{hour} = $ehour;
 	    $iml_worst_event{desc} = $edesc;
	    $iml_worst_event{level} = $elevel;
 	    print "DD: this is worst than previous\n" if $opt_verbose ge 2;
 	}
    } else {
	print "DD: unknown event: $_\n" if $opt_verbose ge 2;
    }
}

my %states = (
	'NONE' => 'UNKNOWN',
	'INFO' => 'OK',
	'REPAIRED' => 'WARNING',
	'CAUTION' => 'WARNING',
	'CRITICAL' => 'CRITICAL'
	);

print "- hp.hardware.hpiml $exit_codes{$states{$iml_worst_event{level}}}\n";
