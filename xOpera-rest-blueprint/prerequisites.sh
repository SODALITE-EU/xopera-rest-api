#!/bin/bash
PIP_INSTALLED=$(which pip3)
if [ -z "$PIP_INSTALLED" ]; then
    echo
    echo
    read -p "pip3 is not installed. Do you wish to update and install pip? " ynp
    if [ "$ynp" != "${ynp#[Yy]}" ] ;then
        echo
        echo "Installing pip3"
    else
        echo
        echo "Abort."
        return
    fi
    sudo apt update
    sudo apt install -y python3 python3-pip
fi

OPERA_INSTALLED=$(pip3 show opera)

if [ -z "$OPERA_INSTALLED" ]; then
    echo
    echo
    read -p "xOpera is not installed. Do you wish to update and install xOpera and required packages? " yn
    if [ "$yn" != "${yn#[Yy]}" ] ;then
        echo
        echo "Installing xOpera"
    else
        echo
        echo "Abort."
        return
    fi
    sudo apt update
    sudo apt install -y python3-venv python3-wheel python-wheel-common
    sudo apt install -y ansible
    python3 -m venv --system-site-packages .venv && . .venv/bin/activate
    pip3 install opera
fi

echo
echo "Installing required Ansible roles"
ansible-galaxy install geerlingguy.docker --force
ansible-galaxy install geerlingguy.pip --force
ansible-galaxy install geerlingguy.repo-epel --force

echo
echo "Cloning modules"
rm -r -f modules/
git clone https://github.com/SODALITE-EU/iac-modules.git modules/

echo "Please enter email for SODALITE certificate: "
read EMAIL_INPUT
export SODALITE_EMAIL=$EMAIL_INPUT

echo "Checking TLS key and certificate..."
FILE_KEY=modules/docker/artifacts/ca.key
if [ -f "$FILE_KEY" ]; then
    echo "TLS key file already exists."
else
    echo "TLS key does not exist. Generating..."
    openssl genrsa -out $FILE_KEY 4096
fi
FILE_CRT=modules/docker/artifacts/ca.crt
if [ -f "$FILE_CRT" ]; then
    echo "TLS certificate file already exists."
else
    echo "TLS certificate does not exist. Generating..."
    openssl req -new -x509 -key $FILE_KEY -out $FILE_CRT -subj "/C=SI/O=XLAB/CN=$SODALITE_EMAIL" 2>/dev/null
fi

unset SODALITE_EMAIL