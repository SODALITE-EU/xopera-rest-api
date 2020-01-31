#!/bin/bash
local_ip="$1"
registry_ip="$2"

cd Certs || exit

echo "generating client certificates for local computer..."
./generate_noprompt.sh "$local_ip" IP:"$local_ip" local
echo "done."


echo "adding ca.crt to ca-certificates..."
cp ca.crt /usr/share/ca-certificates/ca.crt
echo "ca.crt" >> /etc/ca-certificates.conf
update-ca-certificates

echo "copying client certs to /etc/docker/certs.d"

if [ ! -d "/etc/docker/certs.d/" ]; then
  mkdir /etc/docker/certs.d
fi

rm -rf "/etc/docker/certs.d/${registry_ip}"
mkdir "/etc/docker/certs.d/${registry_ip}"
cp ca.crt "/etc/docker/certs.d/${registry_ip}/ca.crt"
cp "local/${local_ip}.crt" "/etc/docker/certs.d/${registry_ip}/client.cert"
cp "local/${local_ip}.key" "/etc/docker/certs.d/${registry_ip}/client.key"

echo "done."
