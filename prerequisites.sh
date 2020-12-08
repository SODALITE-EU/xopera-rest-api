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
ansible-galaxy install -r requirements.yml --force

echo
echo "Cloning modules"
rm -r -f xOpera-rest-blueprint/modules/
git clone https://github.com/SODALITE-EU/iac-modules.git xOpera-rest-blueprint/modules/