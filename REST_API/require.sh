#!/bin/bash

apt install -y python3-venv python3-wheel python-wheel-common python3 python3-pip libpq-dev musl-dev libffi-dev libssl-dev ansible docker.io python3-flask
pip3 install -U wheel "opera[openstack]<0.5" Flask flask_restplus psycopg2 jinja2 docker-py
sudo ansible-galaxy install -r Implementation/scripts/requirements.yml