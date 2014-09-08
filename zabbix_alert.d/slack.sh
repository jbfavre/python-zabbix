#!/bin/bash

# zabbix2slack.sh webhook script
# Copyright 2014 Jean Baptiste Favre <jean-baptiste.favre@blablacar.com>
#
# This script can be used as Zabbix media types to send Zabbix alert to Slack
# It uses Slack API to send JSON formatted messages. Display is customized
# with attachement (https://api.slack.com/docs/attachments)
#
# You should also configure a specific Zabbix action with following parameters:
#
####################
# Name: Production issue - Slack
#
# Default subject: {TRIGGER.STATUS}-{TRIGGER.SEVERITY}
# Default message: Alert: {TRIGGER.NAME}\nHost: {HOSTNAME} ({IPADDRESS})
#
# Recovery subject: {TRIGGER.STATUS}-{TRIGGER.SEVERITY}
# Recovery message: Alert: {TRIGGER.NAME}\nHost: {HOSTNAME} ({IPADDRESS})
####################
#
# Values received by this script:
# To = $1 (Slack.com incoming web-hook token, specified in the Zabbix web interface)
# Subject = $2 (this script assume subject is {TRIGGER.STATUS}-{TRIGGER.SEVERITY})
# Message = $3 (whatever message Zabbix sends, like "Zabbix server is unreachable for 5 minutes - Zabbix server (127.0.0.1)")
#

# Slack sub-domain name (without '.slack.com'), user name, and the channel to send the message to
subdomain='you_subdomain'
channel='#channel_name'
username='Zabbix'

# Associative array to deal with colors
declare -A severityArray=(
  ["Not_classified"]="#DBDBDB"
  ["Information"]="#D6F6FF"
  ["Warning"]="#FFF6A5"
  ["Average"]="#FFB689"
  ["High"]="#FF9999"
  ["Disaster"]="#FF3838"
)

# Get the Slack incoming web-hook token ($1) and Zabbix subject ($2 - hopefully either PROBLEM or RECOVERY)
token="$1"
strSubject="$2"

# Extract status & severity from subject:
# * status [OK|PROBLEM]
# * severity [Not classified|Information|Warning|Average|High|Disaster]
arrSubject=(${strSubject//-/ })
status=${arrSubject[0]}
severity=${arrSubject[1]}

# Change message emoji depending on the status - smile (RECOVERY), frowning (PROBLEM), or ghost (for everything else)
emoji=':ghost:'
color='#FFFFFF'
if [ "$status" == 'OK' ]; then
  emoji=':smile:'
  color='good'
  title=${status}
elif [ "$status" == 'PROBLEM' ]; then
  emoji=':scream:'
  color=${severityArray["${severity// /_}"]}
  title=${severity}
fi

# Prepare attachment payload so that we can customize
# how Slack will display allert
attachment="
{
  \"title\":\"${title}\",
  \"fallback\":\"*${title}*\n$3\",
  \"text\":\"$3\",
  \"color\":\"${color}\",
  \"mrkdwn_in\": [\"text\", \"title\", \"fallback\"]
}"

# Build our JSON payload and send it as a POST request to the Slack incoming web-hook URL
payload="payload={\"channel\": \"${channel}\", \"username\": \"${username}\", \"icon_emoji\": \"${emoji}\", \"attachments\":[${attachment}]}"
/usr/bin/curl -m 5 --data "${payload}" "https://${subdomain}.slack.com/services/hooks/incoming-webhook?token=${token}"
