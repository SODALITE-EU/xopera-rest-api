#!/bin/bash

path="$1"
id="$2"
logfile="$3"
blueprint_token="$4"
session_token="$5"
timestamp_start="$6"
timestamp_blueprint="$7"
inputs_file="$8"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/.." || exit

password="$(ansible-vault view --vault-id prod@settings/sec.yml settings/vault.yml)"
cd "$path" || exit                     #full path
{
echo "Adding openrc key"
. openrc.sh <<<"$password" #password
echo "Entered"
echo "Launching xOpera"

if [ -z "$inputs_file" ]
then
    opera deploy "$id" service.yaml

else
    opera deploy -i "$inputs_file" "$id" service.yaml
fi

echo "finalizing deployment"
# echo "$PWD"
} &> "$logfile"
cd "../../"

python3 finalize_deployment.py deploy "$path" "$id" "$logfile" "$blueprint_token" "$session_token" "$timestamp_start" "$timestamp_blueprint" "$inputs_file"