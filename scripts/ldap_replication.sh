#!/bin/bash

master="<MASTER_IP>:<MASTER_PORT>"
slave="<SLAVE_IP>:<SLAVE_PORT>"

base="dc=company,dc=tld"
binddn="cn=<USER>,dc=company,dc=tld"
bindpw="<PASSWORD>"

getCSN()
{
    uri=$1
    ldapsearch -x -D $binddn -w $bindpw -LLL -H ldap://$uri -s base -b $base contextCSN | grep ^contextCSN: | awk -F ': ' '{print $2}'
}

masterCSN=$( getCSN $master )
slaveCSN=$( getCSN $slave )

if [ x"$masterCSN" = x"$slaveCSN" ]; then
    echo 1
else
    echo 0
fi
exit 0
