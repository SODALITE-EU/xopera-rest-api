#!/bin/bash
cd "${0%/*}/" || exit

sudo mkdir -p /home/xopera/certs
sudo cp -rf ../Certs/ca.crt /home/xopera/certs/ca.crt
sudo cp -rf ../Certs/ca.key /home/xopera/certs/ca.key
for FILE in ../Certs/firstdeploy/*.crt; do sudo cp -rf "$FILE" "/home/xopera/certs/xopera.local.crt"; done
for FILE in ../Certs/firstdeploy/*.key; do sudo cp -rf "$FILE" "/home/xopera/certs/xopera.local.key"; done


sudo cp -rf ../Builds/. /home/xopera/build/

sudo cp -rf ../Certs/ca.crt /usr/local/share/ca-certificates/ca-xopera.crt
sudo update-ca-certificates

export FLASK_APP="run.py"
export FLASK_DEBUG=1
export FLASK_ENV=development
flask run
