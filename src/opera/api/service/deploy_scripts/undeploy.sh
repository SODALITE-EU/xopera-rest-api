#!/bin/bash

path="$1"
logfile="$2"
timestamp_start="$3"
interpreter="$4"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/../.." || exit

cd "$path" || exit
{
echo "Launching xOpera"
opera undeploy

echo $?
} &> "$logfile"
cd "../../../../../"

"$interpreter" -m opera.api.finalize_deployment undeploy "$path" "$timestamp_start"