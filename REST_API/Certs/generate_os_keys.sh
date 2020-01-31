#!/bin/bash

IP="$1"

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
ssh-keygen -t rsa -f "${IP}-xOpera" -q -N ""
mv "${IP}-xOpera" "${IP}-xOpera.pk"
mv "${IP}-xOpera.pub" "${IP}-xOpera.pubk"
echo "Done."