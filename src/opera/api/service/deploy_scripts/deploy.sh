#!/bin/bash

path="$1"
logfile="$2"
timestamp_start="$3"
inputs_file="$4"
interpreter="$5"
entry_definitions="$6"

eval "$(ssh-agent)" >>"/dev/null"
cd "${0%/*}/../.." || exit

cd "$path" || exit
{
echo "Launching xOpera"

if [ -z "$inputs_file" ]
then
    opera deploy "$entry_definitions"

else
    opera deploy -i "$inputs_file" "$entry_definitions"
fi

echo $?

} &> "$logfile"
cd "../../../../../"

"$interpreter" -m opera.api.finalize_deployment deploy "$path" "$timestamp_start" "$inputs_file"