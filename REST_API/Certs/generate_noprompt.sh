rm -rf "$3/"
mkdir "$3/"
openssl genrsa -out "$3/$1.key" 4096
openssl req -new -sha256 -key "$3/$1.key" -subj "/emailAddress=dragan.radolovic@xlab.si/C=SL/ST=SI/L=Ljubljana/O=XLAB/OU=Research/CN=$1" -addext "subjectAltName = $2" -out "$3/$1.csr"
openssl x509 -req -in "$3/$1.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -out "$3/$1.crt" -days 800 -sha256
chmod 755 "$3/"
chmod 644 "$3/$1.key"
chmod 644 "$3/$1.crt"