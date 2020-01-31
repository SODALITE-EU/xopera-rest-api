path_to_CA_dir="$1"
path_to_csr="$2"

keyname=$(basename "$path_to_csr")
keyname="${keyname%.*}"

openssl x509 -req -in "$path_to_csr" -CA "${path_to_CA_dir}/ca.crt" -CAkey "${path_to_CA_dir}/ca.key" -CAcreateserial -out "${keyname}.crt" -days 800 -sha256