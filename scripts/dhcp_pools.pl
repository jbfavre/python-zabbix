#!/usr/bin/perl
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

use strict;
use Getopt::Long;
use Socket qw(inet_aton);
use Time::Local qw(timegm);
use DB_File;
use Pod::Usage;

#---------------------------------------------------------------------
# Global variables
#---------------------------------------------------------------------

# Version information
my $VERSION = '0.2';

# Two hashes were all info found in the dhcpd.conf and dhcpd.leases
# files are stored
my %subnet = ();
my %lease  = ();

# Options with default values
my %opt = ( 'config'       => '/etc/dhcp/dhcpd.conf',
	    'leases'       => '/var/lib/dhcp/dhcpd.leases',
	    'munin'        => 0,
	    'pool'         => q{},
	    'append'       => q{},
	    'nagios'       => 0,
	    'zabbix'       => 0,
	    'zabbix-discovery' => 0,
	    'verbose'      => 0,
	    'help'         => 0,
	    'version'      => 0,
	    'cache-period' => 5,
	  );

# IP address regexp (not really precise, but close enough)
my $ip_regexp = qr{
		      \d{1,3} [.]
		      \d{1,3} [.]
		      \d{1,3} [.]
		      \d{1,3}
	      }xms;

# Get options from command line
GetOptions ( "c|config=s"     => \$opt{'config'},
	     "leases=s"       => \$opt{'leases'},
	     "m|munin"        => \$opt{'munin'},
	     "pool=s"         => \$opt{'pool'},
	     "append=s"       => \$opt{'append'},
	     "nagios"         => \$opt{'nagios'},
	     "snmp"           => \$opt{'snmp'},
	     "v|verbose"      => \$opt{'verbose'},
	     "help"           => \$opt{'help'},
	     "man"            => \$opt{'man'},
	     "version"        => \$opt{'version'},
	     "cache-period=i" => \$opt{'cache_period'},
       "zabbix"         => \$opt{'zabbix'},
       "zabbix-discovery"         => \$opt{'zabbix-discovery'},
	   ) or exit 1;

my $cache_dir  = '/tmp/dhcpd-pool'; # handy for debugging
#my $cache_dir  = '/var/cache/dhcpd-pool';
my $cache_file = $cache_dir . '/cache.db';


#=====================================================================
# Main program
#=====================================================================

# If user requested help
if ($opt{'help'}) {
    pod2usage(0);
}

# If user requested man page
if ($opt{'man'}) {
    pod2usage(-exitstatus => 0, -verbose => 2);
}

# If user requested version info
if ($opt{'version'}) {
    print "dhcpd-pool version $VERSION\n";
    exit 0;
}

# If munin option is specified, set options the Munin way
if ($opt{'munin'}) {
    $opt{'config'} = $ENV{'configfile'} ? $ENV{'configfile'} : $opt{'config'};
    $opt{'leases'} = $ENV{'leasefile'}  ? $ENV{'leasefile'}  : $opt{'leases'};
}

# Check and possibly create the cache dir
if (! -d $cache_dir) {
    mkdir $cache_dir, 0700
      or die "Couldn't create cache directory $cache_dir: $!\n";
}

# Stat the cache file, and if mtime is less than the cache period in
# the past, read the cache instead of the config and leases files
my @cstat = stat($cache_file);
if ( (time() - $cstat[9]) < ($opt{'cache_period'} * 60) ) {
    read_cache();                # read cache
}
else {
    read_config($opt{'config'}); # read config file
    read_leases();               # read leases file
    write_cache();               # write cache
}

# Behaviour depending on options
if ($opt{'nagios'}) {
    # Act as Nagios plugin
    my $retval = nagios_plugin();
    exit $retval;
}
elsif ($opt{'munin'}) {
    # Act as a Munin plugin
    my $retval = munin_plugin();
    exit $retval;
}
elsif ($opt{'zabbix'}) {
    # Act as a Zabbix plugin
    # update metrics
    my $retval = zabbix_plugin();
    exit $retval;
}
elsif ($opt{'zabbix-discovery'}) {
    # Act as a Zabbix plugin
    # update metrics
    my $retval = zabbix_plugin('discovery');
    exit $retval;
}
else {
    # Default behaviour
    print_status();
}


#---------------------------------------------------------------------
# Functions
#---------------------------------------------------------------------

# Writes the cache file. Uses a Berkeley DB via DB_File
sub write_cache {

    # Delete cache file
    unlink $cache_file;

    # The cache hash
    my %cache = ();

    # Open the cache file
    my $db = tie %cache, 'DB_File', $cache_file, O_CREAT|O_RDWR, 0600, $DB_HASH
      or die "Cannot open file '$cache_file': $!\n";

    # Write config to cache
    foreach my $net (keys %subnet) {
	my $mask = $subnet{$net}{'mask'};
	foreach my $pool (keys %{ $subnet{$net}{'pool'} }) {
	    foreach my $key (qw(name warning critical monitor)) {
		my $ckey = join('__CaChEiD__', '0', join('__SuBnEt__', $net, $mask, $pool, $key));
		$cache{$ckey} = $subnet{$net}{'pool'}{$pool}->{$key};
	    }
	}
    }

    # Write lease info to cache
    foreach my $ip (keys %lease) {
	foreach my $key (qw(pool state)) {
	    my $ckey = join('__CaChEiD__', '1', join('__LeAsE__', $ip, $key));
	    $cache{$ckey} = $lease{$ip}{$key};
	}
    }

    # Cleanup
    undef $db;
    untie %cache;
}

# Reads the cache file. Uses a Berkeley DB via DB_File
sub read_cache {

    # The cache hash
    my %cache = ();

    # Open the cache file
    my $db = tie %cache, 'DB_File', $cache_file, O_RDONLY, 0600, $DB_HASH
      or die "Cannot tie '$cache_file': $!\n";

    # Read config and leases from cache
    foreach my $key (keys %cache) {
	my ($id, $rest) = split(/__CaChEiD__/, $key);
	if ($id == 0) {
	    my ($net, $mask, $pool, $attr) = split(/__SuBnEt__/, $rest);
	    $subnet{$net}{'mask'} = $mask;
	    $subnet{$net}{'pool'}{$pool}{$attr} = $cache{$key};
	}
	elsif ($id == 1) {
	    my ($ip, $attr) = split(/__LeAsE__/, $rest);
	    $lease{$ip}{$attr} = $cache{$key};
	}
    }

    # Cleanup
    undef $db;
    untie %cache;
}


# Convert octal subnet mask to its decimal form
# E.g. 255.255.255.0 = 24
sub convert_netmask {
    my $subnetmask = shift;

    my $mask = 0;

    foreach my $oct ( split('\.', $subnetmask) ) {
	for (my $i = 0; $i < 8; ++$i) {
	    ++$mask if ($oct & 2**$i) == (2**$i);
	}
    }

    return $mask;
}


#
# Read the DHCP configuration file. Whenever we find a pool
# declaration, monitoring information (i.e. warning and critical limits),
# the IP range and subnet information is stored.
#
# This function is recursive, to take into account "include"
# statements in the configuration file.
#
sub read_config {
    my $cf = shift;

    # Limit declaration regexp (semi-evil and obscure)
    # Example: # monitor: 80% 90% Y My subnet
    my $limit_regexp = qr{
			   \#       \s*?  # Comment sign
			   monitor: \s+?  # monitor:
			   (-{0,1})       # Optional minus sign
			   (\d+)          # WARNING limit
			   (%{0,1}) \s+?  # Optional percent sign
			   (-{0,1})       # Optional minus sign
			   (\d+)          # CRITICAL limit
			   (%{0,1}) \s+?  # Optional percent sign
			   ([YN])   \s+?  # Y or N
			   ([^\n]*)       # Name of pool (optional)
		     }ixms;

    # Subnet declaration regexp
    # Example: subnet 129.240.202.0 netmask 255.255.254.0 {
    my $subnet_regexp = qr{
			      \A           \s*
			      subnet       \s+
			      ($ip_regexp) \s+
			      netmask      \s+
			      ($ip_regexp)
		      }xms;

    # Range declaration regexp
    # Examples: range 129.240.203.200 129.240.203.246;
    #           range 129.240.203.187;
    my $range_regexp = qr{
			     \A                  \s*
			     range               \s+
			     ($ip_regexp)        \s*
			     (($ip_regexp){0,1}) \s*
			     ;
		     }xms;


    recursive_read_config($cf);

    # The recursive part
    sub recursive_read_config {
	$cf = shift;

	my $count    = 0;
	my $scope    = q{};
	my $net      = q{};
	my $mask     = q{};
	my $name     = q{};
	my %warning  = ('pool' => q{}, 'subnet' => q{});
	my %critical = ('pool' => q{}, 'subnet' => q{});
	my %monitor  = ('pool' => q{}, 'subnet' => q{});

	# Open and read the configuration file
	open my $CONF, '<', $cf
	  or die "Couldn't open config file ($cf): $!\n";
	while (<$CONF>) {

	    # Found an include statement. Call ourself recursively
	    if (m/\A\s* include \s+ ['"](.*?)['"];/xms) {
		my $newcf = $1;
		#$newcf =~ s{/etc/dhcpd.conf.d/}{}; # handy for debugging
		recursive_read_config($newcf);
	    }

	    # Found a subnet declaration
	    elsif (m{$subnet_regexp}xms) {

		$net  = $1;
		$mask = convert_netmask($2);

		# We're inside a subnet scope
		$scope = 'subnet';

		# store subnet info
		$subnet{$net}{'mask'} = $mask;

		# reset pool count
		$count = 0;
	    }

	    # Found a pool declaration
	    elsif (m/\A \s* pool \s* \{/xms) {

		# We're inside a pool scope
		$scope = 'pool';

		# increase the pool count
		++$count;
	    }

	    # Found a limit statement
	    elsif (m{$limit_regexp}xms) {

		$warning{$scope}  = $1 . $2 . $3;
		$critical{$scope} = $4 . $5 . $6;
		$monitor{$scope}  = $7;
		$name             = $8;
		chomp $name;
	    }

	    # Found a range declaration
	    elsif (m{$range_regexp}xms) {

		# store pool info
		if ($scope eq 'pool' and $monitor{'pool'} ne q{}) {
		    $subnet{$net}{'pool'}{$count}{'warning'}  = $warning{'pool'};
		    $subnet{$net}{'pool'}{$count}{'critical'} = $critical{'pool'};
		    $subnet{$net}{'pool'}{$count}{'monitor'}  = $monitor{'pool'};
		}
		else {
		    $subnet{$net}{'pool'}{$count}{'warning'}  = $warning{'subnet'};
		    $subnet{$net}{'pool'}{$count}{'critical'} = $critical{'subnet'};
		    $subnet{$net}{'pool'}{$count}{'monitor'}  = $monitor{'subnet'};
		}

		#$name = 'Anonymous' if $scope eq 'subnet';
		$name = 'Anonymous' if $name eq q{};

		$subnet{$net}{'pool'}{$count}{'name'} = $name;

		if ($2 eq q{}) {
		    $lease{$1}->{'pool'} = "$net/$mask/$count";
		}
		else {
		    foreach my $ip ( @{ explode_range($1, $2) } ) {
			$lease{$ip}->{'pool'} = "$net/$mask/$count";
		    }
		}
	    }

	    # End of pool
	    elsif ($scope eq 'pool' and m@\}@) {
		$scope = 'subnet';

		#reset variables
		$name             = q{};
		$warning{'pool'}  = q{};
		$critical{'pool'} = q{};
		$monitor{'pool'}  = q{};
	    }

	    # End of subnet
	    elsif ($scope eq 'subnet' and m@\}@) {
		$scope = q{};

		# reset variables
		$net                = q{};
		$mask               = q{};
		$name               = q{};
		$warning{'subnet'}  = q{};
		$critical{'subnet'} = q{};
		$monitor{'subnet'}  = q{};
	    }
	}
	close $CONF;
    }
}


#
# Explode the range of IP addresses declared in the range
# declaration. Arguments are the "to" and "from" in the range
# declaration. Returns pointer to a list with all IP addresses in the
# range.
#
sub explode_range {
    my $ipaddress1 = shift;
    my $ipaddress2 = shift;

    my @range = ();

    my @ip1 = split('\.', $ipaddress1);
    my @ip2 = split('\.', $ipaddress2);

    my @i = @ip1;
    while (@i[3] != @ip2[3] or @i[2] != @ip2[2]
	   or @i[1] != @ip2[1] or @i[0] != @ip2[0]) {
	push @range, join('.', @i);
	if ($i[3] < 255) {
	    $i[3]++;
	}
	elsif ($i[3] == 255 and $i[2] < 255) {
	    $i[3] = 0;
	    $i[2]++;
	}
	elsif ($i[2] == 255 and $i[1] < 255) {
	    $i[3] = 0;
	    $i[2] = 0;
	    $i[1]++;
	}
	elsif ($i[1] == 255 and $i[0] < 255) {
	    $i[3] = 0;
	    $i[2] = 0;
	    $i[1] = 0;
	    $i[0]++;
	}
	else {
	    die "Range error: IP out of range\n";
	}
    }
    push @range, join('.', @ip2);

    return \@range;
}


#
# Function that reads the dhcpd.leases file. End time for leases are
# calculated and the lease is flagged as either free, expired or
# active (i.e. in use).
#
sub read_leases {

    # Initialize leases
    foreach my $l (keys %lease) {
	$lease{$l}->{'state'} = '-';
    }

    my $valid = 0;      # flag: if a lease is found in a range
    my $pid   = q{};    # pool ID
    my $now   = time(); # current time
    my $ends  = q{};    # lease end time
    my $ip    = q{};    # lease IP number

    # ends regexp
    # Example: ends 5 2008/04/04 10:40:45;
    my $ends_regexp = qr{
			    \A   \s+
			    ends \s
			    \d   \s
			    (\d+)/(\d+)/(\d+) \s
			    (\d+):(\d+):(\d+) ;
		    }xms;

    # Open and read the dhcpd.leases file. Store the lease and
    # relevant information in the %lease hash.
    open my $LEASES, '<', $opt{'leases'}
      or die "Couldn't open leases file ($opt{leases}): $!\n";
    while (<$LEASES>) {
	if (m/^lease ($ip_regexp) \{$/) {
	    $ip = $1;
	  POOL:
	    foreach my $l (keys %lease) {
		if ($l eq $ip) {
		    $valid = 1; # this is a valid lease
		    $pid = $lease{$l}->{'pool'};
		    last POOL;
		}
	    }
	}
	elsif ($valid and m{$ends_regexp}xms) {
	    $ends = timegm($6, $5, $4, $3, $2-1, $1);
	}
	elsif ($valid and /^\s+ends never;$/) {
	    $ends = -1;
	}
	elsif ($valid and /^\}$/) {
	    if ($ends == -1 or $ends >= $now) {
		$lease{$ip}->{'state'} = 'active';
	    }
	    else {
		# A lease can exist several places in the leases
		# file. If one of the entries is active, the others
		# should be ignored
		if ($lease{$ip}->{'state'} ne 'active') {
		    $lease{$ip}->{'state'} = 'expired';
		}
	    }
	    $valid = 0;
	    $ends = q{};
	}
    }
    close $LEASES;
}


#
# Function that does the Nagios stuff
#
sub nagios_plugin {

    my %limit  = ();

  SUBNET:
    foreach my $net (sort by_ip keys %subnet) {
	my $mask = $subnet{$net}{'mask'};

      POOL:
	foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {
	    next POOL if $subnet{$net}{'pool'}{$pool}->{'monitor'} ne 'Y';

	    # Some helper variables
	    my $monitor  = $subnet{$net}{'pool'}{$pool}->{'monitor'};
	    my $warning  = $subnet{$net}{'pool'}{$pool}->{'warning'};
	    my $critical = $subnet{$net}{'pool'}{$pool}->{'critical'};
	    my $name     = $subnet{$net}{'pool'}{$pool}->{'name'};

	    # Summarize active/total leases in pool
	    my $active = 0;
	    my $range = 0;
	    foreach my $l (keys %lease) {
		if ($lease{$l}->{'pool'} eq "$net/$mask/$pool") {
		    ++$range;
		    if ($lease{$l}->{'state'} eq 'active') {
			++$active;
		    }
		}
	    }

	    # Handle the critical and warning limits
	    foreach ( qw(critical warning) ) {
		my $treshold = $subnet{$net}{'pool'}{$pool}->{$_};

		# If limit is given in percent
		if ($treshold =~ m/^(\d+)%$/) {
		    my $lim = $1;
		    my $percent = $active * 100 / $range;
		    if ($percent > $lim) {
			my $line = sprintf("Pool \"%s\" in subnet %s/%s is %.1f%% full",
					   $name, $net, $mask, $percent);
			push @{ $limit{$_} }, $line;
			next POOL;
		    }
		}

		# If limit is given in number of free leases
		elsif ($treshold =~ m/^-(\d+)$/) {
		    my $lim = $1;
		    my $free = $range - $active;
		    if ($free < $lim) {
			my $line = sprintf("Pool \"%s\" in subnet %s/%s has only %d free leases",
					   $name, $net, $mask, $free);
			push @{ $limit{$_} }, $line;
			next POOL;
		    }
		}

		# If limit is given in number of leases in use
		elsif ($treshold =~ m/^(\d+)$/) {
		    my $lim = $1;
		    if ($active > $lim) {
			my $line = sprintf("Pool \"%s\" in subnet %s/%s has %d active leases (of total %d)",
					   $name, $net, $mask, $active, $range);
			push @{ $limit{$_} }, $line;
			next POOL;
		    }
		}
	    }
	}
    }

    # Print the criticals, if any
    foreach (@{ $limit{'critical'} }) {
	print "$_\n";
    }

    # Print the warnings, if any
    foreach (@{ $limit{'warning'} }) {
	print "$_\n";
    }

    # Determine proper return value
    #  (critical = 2, warning = 1, normal = 0)
    my $retval = 0;
    if (scalar(@{ $limit{'critical'} }) > 0) {
	$retval = 2;
    }
    elsif (scalar(@{ $limit{'warning'} }) > 0) {
	$retval = 1;
    }

    return $retval;
}


#
# Function that implements the Munin feature
#
sub munin_plugin {

    # Suggest option
    if ($opt{'append'} eq 'suggest') {
	foreach my $net (sort by_ip keys %subnet) {
	  POOL:
	    foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {
		next POOL if $subnet{$net}{'pool'}{$pool}->{'monitor'} ne 'Y';
		print join('_', $net, $subnet{$net}{'mask'}, $pool) . "\n";
	    }
	}
	return 0;
    }

    # Count number of active leases in each pool
    foreach my $net (keys %subnet) {
	foreach my $pool (keys %{ $subnet{$net}{'pool'} }) {
	    # Initialize
	    $subnet{$net}{'pool'}{$pool}{'active'} = 0;
	    $subnet{$net}{'pool'}{$pool}{'range'}  = 0;

	    # Summarize
	    foreach my $l (keys %lease) {
		if ($lease{$l}{'pool'} eq join('/', $net, $subnet{$net}{'mask'}, $pool)) {
		    $subnet{$net}{'pool'}{$pool}{'range'}++;
		    if ($lease{$l}->{'state'} eq 'active') {
			$subnet{$net}{'pool'}{$pool}{'active'}++;
		    }
		}
	    }
	}
    }

    # Graph with all pools
    if ($opt{'pool'} eq 'total') {

	# If config is requested
	if ($opt{'append'} eq 'config') {
	    my %label = ();

	    print "graph_title All DHCP pools\n";
	    print "graph_args --base 1000\n";
	    print "graph_vlabel % full\n";
	    print "graph_category DHCP\n";
	    print "graph_order";

	    foreach my $net (sort by_ip keys %subnet) {
	      POOL:
		foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {
		    next POOL if $subnet{$net}{'pool'}{$pool}->{'monitor'} ne 'Y';
		    my $lab = $net;
		    $lab =~ s/\./_/g;

		    print " " . join('_', $lab, $subnet{$net}{'mask'}, $pool);
		    $label{join('_', $lab, $subnet{$net}{'mask'}, $pool)}
		      = $subnet{$net}{'pool'}{$pool}->{'name'};
		}
	    }
	    print "\n";
	    foreach my $l (keys %label) {
		my $lab = $l;
		$lab =~ s/\./_/g;
		print "$lab.label $label{$l}\n";
		print "$lab.min 0\n";
		print "$lab.max 100\n";
	    }
	    return 0;
	}

	# If values are requested
	else {
	    foreach my $net (sort by_ip keys %subnet) {
	      POOL:
		foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {
		    next POOL if $subnet{$net}{'pool'}{$pool}->{'monitor'} ne 'Y';
		    my $lab = $net;
		    $lab =~ s/\./_/g;
		    print join('_', $lab, $subnet{$net}{'mask'}, $pool)
		      . '.value '
			. $subnet{$net}{'pool'}{$pool}{'active'} * 100 / $subnet{$net}{'pool'}{$pool}{'range'}
			  . "\n";
		}
	    }
	    return 0;
	}
    }

    # Identify which pool the user wants to graph
    my ($net, $pool);
  SUBNET:
    foreach my $n (keys %subnet) {
	foreach my $p (keys %{ $subnet{$n}{'pool'} }) {
	    if ($opt{'pool'} eq join('_', $n, $subnet{$n}{'mask'}, $p)) {
		$net = $n;
		$pool = $p;
		last SUBNET;
	    }
	}
    }

    # If pool is monitored, get warning/critical values
    my %val = ('warning' => 0, 'critical' => 0);
    if ($subnet{$net}{'pool'}{$pool}{'monitor'} eq 'Y') {
	foreach (qw(warning critical)) {
	    my $lim = $subnet{$net}{'pool'}{$pool}->{$_};
	    if ($lim =~ m/^(\d+)%$/) {
		$val{$_} = ($1 / 100) * $subnet{$net}{'pool'}{$pool}{'range'};
	    }
	    elsif ($lim =~ m/^-(\d+)$/) {
		$val{$_} = $subnet{$net}{'pool'}{$pool}{'range'} - $1;
	    }
	    elsif ($lim =~ m/^(\d+)$/) {
		$val{$_} = $1;
	    }
	}
    }

    # If config is requested
    if ($opt{'append'} eq 'config') {
	print "graph_title DHCP leases in \"" . $subnet{$net}{'pool'}{$pool}{'name'} . "\"\n";
	print "graph_args --base 1000 -v leases -l 0\n";
	print "graph_category DHCP\n";
	print "active.info Number of active leases\n";
	print "active.draw AREA\n";
	print "active.min 0\n";
	print "active.max $subnet{$net}{pool}{$pool}{range}\n";
	print "active.label Active leases\n";

	# If pool is monitored, include warning/critical tresholds
	if ($subnet{$net}{pool}{$pool}{'monitor'} eq 'Y') {
	    print "warning.label Warning at $subnet{$net}{pool}{$pool}{warning}\n";
	    print "warning.min 0\n";
	    print "warning.max $subnet{$net}{pool}{$pool}{range}\n";
	    print "warning.info Warning treshold\n";
	    print "critical.label Critical at $subnet{$net}{pool}{$pool}{critical}\n";
	    print "critical.min 0\n";
	    print "critical.max $subnet{$net}{pool}{$pool}{range}\n";
	    print "critical.info Critical treshold\n";
	}

	print "max.label Total leases\n";
	print "max.min 0\n";
	print "max.max $subnet{$net}{pool}{$pool}{range}\n";
	print "max.info Total number of leases in range\n";

	# If pool is monitored, include warning/critical tresholds
	if ($subnet{$net}{'pool'}{$pool}{'monitor'} eq 'Y') {
	    printf ("active.warning %.1f\n", $val{'warning'});
	    printf ("active.critical %.1f\n", $val{'critical'});
	}
    }

    # If values are requested
    else {
	print "active.value $subnet{$net}{pool}{$pool}{active}\n";

	# If pool is monitored, include warning/critical tresholds
	if ($subnet{$net}{'pool'}{$pool}{'monitor'} eq 'Y') {
	    printf ("warning.value %.1f\n", $val{'warning'});
	    printf ("critical.value %.1f\n", $val{'critical'});
	}

	print "max.value $subnet{$net}{pool}{$pool}{range}\n";
    }
    return 0;
}

#
# Function that implements the Zabbix feature
#
sub zabbix_plugin {
  my $action = @_[0];
  my @poolinfos  = ();

  SUBNET:
  foreach my $net (sort by_ip keys %subnet) {
    my $mask = $subnet{$net}{'mask'};

    POOL:
    foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {
      next POOL if $subnet{$net}{'pool'}{$pool}->{'monitor'} ne 'Y';

      # Some helper variables
      my $monitor  = $subnet{$net}{'pool'}{$pool}->{'monitor'};
      my $warning  = $subnet{$net}{'pool'}{$pool}->{'warning'};
      my $critical = $subnet{$net}{'pool'}{$pool}->{'critical'};
      my $name     = $subnet{$net}{'pool'}{$pool}->{'name'};

      # Summarize active/total leases in pool
      my $active = 0;
      my $range = 0;
      foreach my $l (keys %lease) {
        if ($lease{$l}->{'pool'} eq "$net/$mask/$pool") {
          ++$range;
          if ($lease{$l}->{'state'} eq 'active') {
            ++$active;
          }
        }
      }

      my $free = $range - $active;
      push @poolinfos, {
        'name'     => $name,
        'warning'  => $warning,
        'critical' => $critical,
        'active'   => $active,
        'free'     => $free,
        'total'    => $range
      };
      next POOL;

    }
  }
  if ($action eq 'discovery') {
    # discovery
    my $first = 1;
    print "- dhcp.pools.discovery {\"data\":[";
    foreach my $poolinfo ( @poolinfos ) {
      print "," if not $first;
      $first = 0;
      print "{\"{#DHCPOOLNAME}\":\"".$poolinfo->{name}."\",";
      print "\"{#DHCPOOLWARNING}\":\"".$poolinfo->{warning}."\",";
      print "\"{#DHCPOOLCRITICAL}\":\"".$poolinfo->{critical}."\"}";
    }
    print "]}\n";
  }else{
    # update-items
    foreach my $poolinfo ( @poolinfos ) {
      printf("- \"dhcp.pools[%s,total_lease]\" %d\n",
        $poolinfo->{name}, $poolinfo->{total});
      printf("- \"dhcp.pools[%s,active_lease]\" %d\n",
        $poolinfo->{name}, $poolinfo->{active});
      printf("- \"dhcp.pools[%s,free_lease]\" %d\n",
        $poolinfo->{name}, $poolinfo->{free});
    }
  }
  return 0;

}

# Sort by IP address
sub by_ip {
    (inet_aton($a) || 0) cmp (inet_aton($b) || 0);
}


#
# This function prints various status information
#
sub print_status {
    my $pools_monitored   = 0;
    my $pools_unmonitored = 0;
    my $pools_total       = 0;
    my $lease_total       = 0;
    my $lease_active      = 0;

    foreach my $net (sort by_ip keys %subnet) {

	my $mask = $subnet{$net}{'mask'};

	if (defined $subnet{$net}{'pool'}) {
	    print "\n";
	    print "Subnet $net/$mask\n";
	    print '-' x 50, "\n\n";
	}

	foreach my $pool (sort keys %{ $subnet{$net}{'pool'} }) {

	    # Some helper variables
	    my $monitor  = $subnet{$net}{'pool'}{$pool}->{'monitor'};
	    my $warning  = $subnet{$net}{'pool'}{$pool}->{'warning'};
	    my $critical = $subnet{$net}{'pool'}{$pool}->{'critical'};
	    my $name     = $subnet{$net}{'pool'}{$pool}->{'name'};

	    # Count values
	    ++$pools_total;
	    $monitor eq 'Y'
	      ? ++$pools_monitored
		: ++$pools_unmonitored;

	    # Sum active/free/total leases
	    my $active = 0;
	    my $range = 0;
	    foreach my $l (keys %lease) {
		if ($lease{$l}->{'pool'} eq "$net/$mask/$pool") {
		    ++$range;
		    ++$lease_total;
		    if ($lease{$l}->{'state'} eq 'active') {
			++$active;
			++$lease_active;
		    }
		}
	    }

	    # Print information about pool
	    if ($name eq 'Anonymous') {
		print "  Anonymous pool:\n";
	    }
	    else {
		print "  $pool. Pool \"$name\":\n";
	    }
	    print "\n";
	    print "     Monitoring:      " . ($monitor eq 'Y' ? "ON" : "OFF") . "\n";
	    if ($monitor eq 'Y') {
		print "     Warning limit:  " . ($warning =~ m/^-/ ? q{} : q{ }) . "$warning\n";
		print "     Critical limit: " . ($critical =~ m/^-/ ? q{} : q{ }) . "$critical\n";
	    }
	    printf ("     Active leases:   %d/%d (%.1f\%)\n",
		    $active, $range, ($active * 100 / $range) );

	    # Print IP range if verbose
	    if ($opt{'verbose'}) {
		print "     IP range ($range addresses):\n";
		foreach my $l (sort by_ip keys %lease) {
		    if ($lease{$l}->{'pool'} eq "$net/$mask/$pool") {
			print "       $l\t" . $lease{$l}->{'state'} . "\n";
		    }
		}
	    }

	    print "\n";
	}
    }

    # Print a short summary at the end
    print "\nSUMMARY\n";
    print '=' x 50 . "\n\n";
    print "  Total pools:              $pools_total\n";
    print "  Total pools monitored:    $pools_monitored\n";
    print "  Total pools un-monitored: $pools_unmonitored\n";
    print "\n";
    print "  Total leases:             $lease_total\n";
    printf ("  Total active leases:      %d (%.1f%%)\n",
      $lease_active, ($lease_active * 100 / $lease_total) );
    print "\n";
}

__END__

=head1 NAME

dhcpd-pool - Monitor and report ISC dhcpd pool usage

=head1 SYNOPSIS

dhcpd-pool [-c|--config <configfile>] [-l|--leases <leasefile>]
    [-m|--munin [-p|--pool <poolID>] [-a|--append <string>]]
    [-n|--nagios] [-v|--verbose] [-h|--help]

=head1 DESCRIPTION

This script will report pool usage on a ISC dhcpd server. Does also
work on failover pairs, since each node will have identical config
(when it comes to subnets and pools) and a complete leases file.
Configuration is done in the DHCP config file, but the script will
report usage on pools without configuration. Details below.

The script can operate as a Nagios plugin, reporting pool usage above
the treshold configured by the user. It can also act as a Munin
plugin, creating one graph per pool and/or one graph with all pools.

B<dhcpd-pool> uses a cache file (via Berkeley DB) to speed up runtime
and decrease load impact on the DHCP server. The cache is updated if
it is more than 5 minutes old.

=head1 OPTIONS

=over 4

=item B<-c>, B<--config>

The ISC dhcpd config file. Normally F</etc/dhcpd.conf>, which is the
default.

=item B<-l>, B<--leases>

The ISC dhcpd leases file. Default is F</var/db/dhcpd.leases>

=item B<-n>, B<--nagios>

Act as a Nagios plugin. Notification limits for each pool, as well as
which pools will be monitored, is configured in the DHCP config
file. Details below.

=item B<-m>, B<--munin>

Act as a Munin plugin. One can create one graph per pool, or create
one graph with all pools. In case of the latter percentage usage is
graphed instead of absolute usage, since many different pools in one
graph usually don't make sense and is pretty useless.

=item B<-p>, B<--pool>

Pool ID. This option is only used when acting as a Munin plugin. The
pool ID has the form F<subnet_mask_X> where F<X> is the pool number as
found in the DHCP config file. Pools declared with "pool" starts on 1,
while anonymous pools (without pool declaration) has number 0.
Example: 129.240.202.0_23_1

=item B<-a>, B<--append>

This is the regular Munin option, i.e. "config". Other possibilities
are "suggest" and "autoconf". This option does only make sense when
the script is used as a Munin plugin.

=item B<-v>, B<--verbose>

Be more verbose. This option has only effect when the script is used
in its default form, i.e. not Nagios or Munin. When this option is
given, the IP range for each pool is printed out.

=item B<--cache-period>

The default timeout (or TTL) for the cache, given in minutes. The
default cache period is 5 minutes. You may want to increase this if
you're polling less frequently than the default, in which case the
cache has no effect.

=item B<-h>, B<--help>

Short help text.

=item B<--man>

Display the man page.

=item B<--version>

Display version information

=back

=head1 CONFIGURATION

Configuration is done in the DHCP config file. For each pool you want
to monitor, include a statement like this in the beginning of each
pool scope:

# monitor: <warning> <critical> <Y|N> [name]

Note the comment sign. The limits configuration is a comment in the
DHCP config, and is only recognized by this script.

The B<Y> or B<N> is simply a yes or no to monitoring. If monitoring is
set to B<N>, the Nagios plugin will ignore the pool.

The name is optional, but it's encouraged to set a proper name for
each pool.

The warning and critical limits can each be given in three different
forms. In the examples, if the pool holds 200 leases total, the limits
are effectively identical.

=over 4

=item B<Percentage>

When a percent sign (%) follows the number, the limit is given in
percent. E.g. if the limit is 80% and the pool range contains 200
leases, a notification will occur if the number of active leases is
more than or equal to 160.

Example: # monitor: 80% 90% Y My pool

=item B<Absolute>

When the limit is given as a positive integer, a notification will
occur when the number of active leases is greater than or equal to the
limit.

Example: # monitor: 160 180 Y My pool

=item B<Leases left>

If a minus sign (-) precedes the number, a notification will occur if
the number of free (not active) leases is less than or equal to the
limit.

Example: # monitor: -40 -20 Y My pool

=back

The limit configuration can be set in both the subnet scope and the
pool scope. If set in the pool scope, that takes precedence for that
particular pool. Setting the limits configuration per pool is
recommended.

=head1 FILES

Cache file: F</var/cache/dhcpd-pool/cache.db>

DHCP config: F</etc/dhcpd.conf>

DHCP leases: F</var/db/dhcpd.leases>

=head1 SEE ALSO

Complete documentation: L<http://folk.uio.no/trondham/software/dhcpd-pool.html>

=head1 AUTHOR

Trond H. Amundsen <t.h.amundsen@usit.uio.no>

=head1 BUGS

Probably.

=cut
