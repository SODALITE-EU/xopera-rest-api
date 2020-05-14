#!/bin/bash
DIR=/home/xopera/certs
overwrite_ca="$1"
# overwrite_ca -y: always create new CA cert (overwrite, if needed)
# overwrite_ca -n: do now overwrite CA cert (but create it, if missing)

# create tree...
if [ ! -d "$DIR" ]; then
  echo "Creating tree..."
  mkdir --parents "$DIR"
  chmod 755 "$DIR"
fi


# checking for existing root certificate...
root_ca=true
if [[ -f "$DIR/ca.key" ]] && [[ -f "$DIR/ca.crt" ]]
then

  if test "$overwrite_ca" = "-n";
  then
    echo "Found existing root CA certificate, aborting"
    root_ca=false

  elif test "$overwrite_ca" = "-y";
  then
    echo "Overwriting existing root CA certificate..."

  else
    read -p "Root CA certificate in $DIR already exist, do you want to replace it? [y/n]  " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
      echo "Root CA certificate will be replaced."
    else
      echo "aborting"
      root_ca=false
    fi
  fi

fi


echo "Creating root certificate..."
if [[ "$root_ca" = "true" ]];
then
  rm -f "$DIR/ca.*"
  openssl req -newkey rsa:4096 -nodes -sha256 -keyout "$DIR/ca.key" -x509 -days 800 -out "$DIR/ca.crt"
  chmod 644 "$DIR/ca.key"
  chmod 644 "$DIR/ca.crt"

  sudo cp "$DIR/ca.crt" /usr/share/ca-certificates/ca.crt
  echo "ca.crt" >> /etc/ca-certificates.conf
  update-ca-certificates
fi

echo
echo "Creating client certificates..."
rm -f "$DIR/image.docker.local.*"
openssl genrsa -out "$DIR/image.docker.local.key" 4096
openssl req -new -sha256 -key "$DIR/image.docker.local.key" -subj "/emailAddress=dragan.radolovic@xlab.si/C=SL/ST=SI/L=Ljubljana/O=XLAB/OU=Research/CN=localhost" -out "$DIR/image.docker.local.csr"
# if certificate with other information is needed, line above can be replaced with line below and openssl will ask about it in the process
# openssl req -new -sha256 -key "$DIR/image.docker.local.key"-out "$DIR/image.docker.local.csr"
openssl x509 -req -in "$DIR/image.docker.local.csr" -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial -out "$DIR/image.docker.local.crt" -days 800 -sha256
rm -f "$DIR/image.docker.local.csr"
chmod 644 "$DIR/image.docker.local.key"
chmod 644 "$DIR/image.docker.local.crt"