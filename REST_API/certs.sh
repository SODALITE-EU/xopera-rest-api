#!/bin/bash
COMPUTER_IP="$1"
DOCKER_CONTAINER_IP="$2"

if [[ -z "$COMPUTER_IP" ]] || [[ -z "$DOCKER_CONTAINER_IP" ]];
then
   echo "not enough parameters"
   exit 1
fi

# generate root certificate

printf "generating own CA certificate..."

cd Certs || exit

./generate.sh

echo " done"
printf "generating certificates for docker and signing with own CA..."
# generate other certificates, which will be automatically copied to docker
./generate_noprompt.sh "$COMPUTER_IP" IP:"$DOCKER_CONTAINER_IP" firstdeploy
echo "done"