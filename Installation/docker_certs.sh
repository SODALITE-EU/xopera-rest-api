#!/bin/bash
local_ip="$1" # ip of local computer
registry_ip="$2" # ip of remote registry
root_ca_dir=${3:-/home/xopera/certs} # path to dir with root cert key pair (named ca.key and ca.crt). Default /home/xopera/certs

# CN: common name of xOpera host. Usually IP, but can be arbitrary.
# SSH_DIR: Path to dir with xOpera SSH keys. Must be bind to /root/.ssh on xopera-rest-api container

if [[ $# -gt 3 ]] || [[ $# -lt 1 ]]; then
    echo "Usage: $0 <local_ip> <registry_ip> [root_ca_dir]"
    echo
    echo "positional arguments:"
    echo "  {local_ip, registry_ip, root_ca_dir}"
    echo "    local_ip           IP of local (current) computer"
    echo "    registry_ip        IP of remote registry"
    echo "    root_ca_dir        Path to dir with root cert key pair (named ca.key and ca.crt). Default /home/xopera/certs"
    echo
    exit 1
fi

echo "Installing client certs for connecting to docker registry at ${registry_ip}"

if [ ! -d "/etc/docker/certs.d/" ]; then
  mkdir /etc/docker/certs.d
fi

certs_dir="/etc/docker/certs.d/${registry_ip}"

rm -rf "/etc/docker/certs.d/${registry_ip}"
mkdir "/etc/docker/certs.d/${registry_ip}"
# copy root cert
cp "${root_ca_dir}/ca.crt" "/etc/docker/certs.d/${registry_ip}/ca.crt"
# generate new client cert
openssl genrsa -out "$certs_dir/client.key" 4096
openssl req -new -sha256 -key "$certs_dir/client.key" -subj "/emailAddress=dragan.radolovic@xlab.si/C=SL/ST=SI/L=Ljubljana/O=XLAB/OU=Research/CN=$local_ip" -addext "subjectAltName = IP:$local_ip" -out "$certs_dir/client.csr"
openssl x509 -req -in "$certs_dir/client.csr" -CA "$root_ca_dir/ca.crt" -CAkey "$root_ca_dir/ca.key" -CAcreateserial -out "$certs_dir/client.cert" -days 800 -sha256
rm -f "$certs_dir/client.csr"
chmod 644 "$certs_dir/client.key"
chmod 644 "$certs_dir/client.cert"

echo "done."
