#!/bin/bash

cd "${0%/*}" || exit

rc_file_location="$1"
os_password="$2"
computer_ip="$3"



if [ -z "$rc_file_location" ]; then
  file=openrc.sh || exit
else
  file="$rc_file_location" || exit
fi
echo "OpenStack RC file location: ${rc_file_location}"

echo "Copying OpenStack RC file to settings..."
cp "$file" "Implementation/settings/openrc.sh" || exit
echo "done"


cd Implementation || exit
rm -rf settings/vault.yml || true

if [[ -z "$os_password" ]];
then
   read -s -r -p "Enter OpenStack RC password:" os_password
fi

echo "$os_password" >settings/vault.yml

echo ""
echo "Creting ansible vault and saving openstack pasword..."
ansible-vault encrypt --vault-id prod@settings/sec.yml settings/vault.yml

echo "Vault created"

if [ -z "$computer_ip" ]
then
      exit
fi

echo "Creating OpenStack key pair..."
cd ../Certs || exit
./generate_os_keys.sh "$computer_ip"
echo "done"