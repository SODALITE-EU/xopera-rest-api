#!/bin/bash

CN="$1"
SSH_DIR=${2:-"/root/.ssh"}
# CN: common name of xOpera host. Usually IP, but can be arbitrary.
# SSH_DIR: Path to dir with xOpera SSH keys. Must be bind to /root/.ssh on xopera-rest-api container

if [[ $# -gt 2 ]] || [[ $# -lt 1 ]]; then
    echo "Usage: $0 <CN> [SSH_DIR]"
    echo
    echo "positional arguments:"
    echo "  {CN, SSH_DIR}"
    echo "    CN             Common name of xOpera host. Usually IP, but can be arbitrary."
    echo "    SSH_DIR        Path to dir with xOpera SSH keys. Default is /root/.ssh"
    echo
    exit 1
fi

echo "Installing xOpera SSH key pair..."

skip=false
if [[ $(find "$SSH_DIR" -name "*xOpera*" |  wc -l) -eq 2 ]]
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
    read -p "xOpera ssh keys in $SSH_DIR already exist, do you want to replace them? [y/n]  " -n 1 -r
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
cd "$SSH_DIR"/ || exit
rm -f ./*xOpera*
ssh-keygen -t rsa -f "${CN}-xOpera" -q -N ""
mv "${CN}-xOpera" "${CN}-xOpera.pk"
mv "${CN}-xOpera.pub" "${CN}-xOpera.pubk"
echo "Done."