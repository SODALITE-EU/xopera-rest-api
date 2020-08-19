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
cd "../../../../"
"$interpreter" Implementation/finalize_deployment.py undeploy "$path" "$timestamp_start"