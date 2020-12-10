#!/bin/bash

CN="$1"
# CN: common name of xOpera host. Usually IP, but can be arbitrary.

echo "Installing xOpera SSH key pair..."

skip=false
if [[ $(find /root/.ssh -name "*xOpera*" |  wc -l) -eq 2 ]]
then
  if test "$2" = "-n"; then
    echo "Found xOpera SSH keys, aborting"
    exit
  fi

  if test "$2" = "-y"; then
    echo "Overwriting existing xOpera SSH keys..."
    skip=true
  fi

  if [[ $skip != "true" ]]
  then
    read -p "xOpera ssh keys in /root/.ssh already exist, do you want to replace them? [y/n]  " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
      echo "xOpera keys will be replaced."
    else
      echo "aborting"
      exit
    fi
  fi
fi

echo "Generating rsa key pair for xOpera..."
cd /root/.ssh/ || exit
rm -f ./*xOpera*
ssh-keygen -t rsa -f "${CN}-xOpera" -q -N ""
mv "${CN}-xOpera" "${CN}-xOpera.pk"
mv "${CN}-xOpera.pub" "${CN}-xOpera.pubk"
echo "Done."