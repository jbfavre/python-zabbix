#!/bin/bash

server="<LDAP_IP>:<LDAP_PORT>"

base="dc=company,dc=tld"
binddn="cn=<USER>,dc=company,dc=tld"
bindpw="<PASSWORD>"

checkLDAP()
{
    uri=$1
    ldapsearch -x -D ${binddn} -w ${bindpw} -LLL -H ldap://${uri} -s base -b ${base} 2>&1>/dev/null
}

checkLDAP ${server}
result=$?

if [ $? -eq 0 ]; then
    echo 1
else
    echo 0
fi
exit ${result}
