#!/bin/bash

path="$1"
logfile="$2"
timestamp_start="$3"
inputs_file="$4"
interpreter="$5"
entry_definitions="$6"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/../.." || exit

password="$(ansible-vault view --vault-id prod@settings/sec.yml settings/vault.yml)"
cd "$path" || exit
{
echo "Adding openrc key"
. openrc.sh <<<"$password"
echo "Entered"
echo "Launching xOpera"

if [ -z "$inputs_file" ]
then
    opera deploy "$entry_definitions"

else
    opera deploy -i "$inputs_file" "$entry_definitions"
fi

echo $?

} &> "$logfile"
cd "../../../../"

"$interpreter" Implementation/finalize_deployment.py deploy "$path" "$timestamp_start" "$inputs_file"