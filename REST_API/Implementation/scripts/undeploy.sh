#!/bin/bash

path="$1"
id="$2"
logfile="$3"
blueprint_token="$4"
session_token="$5"
timestamp_start="$6"
timestamp_blueprint="$7"
interpreter="$8"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/.." || exit

password="$(ansible-vault view --vault-id prod@settings/sec.yml settings/vault.yml)"
cd "$path" || exit                     #full path
{
echo "Adding openrc key"
. openrc.sh <<<"$password" #password
echo "Entered"
echo "Launching xOpera"
opera undeploy "$id"               #id
echo "finalizing undeployment"
# echo "$PWD"
} &> "$logfile"
cd "../../../"
"$interpreter" Implementation/finalize_deployment.py undeploy "$path" "$id" "$logfile" "$blueprint_token" "$session_token" "$timestamp_start" "$timestamp_blueprint"