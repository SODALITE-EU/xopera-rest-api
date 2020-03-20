#!/bin/bash

path="$1"
logfile="$2"
timestamp_start="$3"
inputs_file="$4"
interpreter="$5"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/../.." || exit

password="$(ansible-vault view --vault-id prod@settings/sec.yml settings/vault.yml)"
cd "$path" || exit                     #full path
{
echo "Adding openrc key"
. openrc.sh <<<"$password" #password
echo "Entered"
echo "Launching xOpera"

if [ -z "$inputs_file" ]
then
    opera deploy blueprint_id service.yaml

else
    opera deploy -i "$inputs_file" blueprint_id service.yaml
fi

echo "finalizing deployment"
# echo "$PWD"
} &> "$logfile"
cd "../../../../"

"$interpreter" Implementation/finalize_deployment.py deploy "$path" "$timestamp_start" "$inputs_file"