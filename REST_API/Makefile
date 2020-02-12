.PHONY: clean system-packages ansible-packages configure-certs install clean_docker build tests run_docker run all all_docker venv

clean:
	sudo rm -rf Implementation/model_deployment_data/*
	sudo rm -rf Implementation/storage/*

system-packages:
	sudo apt update
	sudo apt install -y python3-venv python3-wheel python-wheel-common python3-pip python3-flask libpq-dev musl-dev libffi-dev libssl-dev ansible docker.io 

system-packages-docker:
	sudo apt update
	sudo apt install -y docker.io

#python-packages:
#	pip3 install --upgrade pip
#	pip3 install -r requirements.txt
#	# pip3 install -U wheel "opera[openstack]<0.5" Flask flask_restplus psycopg2 jinja2 docker-py pytest assertpy

ansible-packages:
	sudo ansible-galaxy install -r Implementation/scripts/requirements.yml

configure-certs: SHELL :=/bin/bash
configure-certs:
	read -rp "Enter computer IP: " computer_ip; \
	read -rp "Enter configuration_script (openrc.sh if using Openstack) path: " rc_file_location; \
	read -srp "Enter openstack pasword: " password; \
	./certs.sh $computer_ip 172.17.0.2; \
	./open_stack_setup.sh $$rc_file_location $$password; \
	sudo ./Certs/generate_os_keys.sh "$$computer_ip"

install: system-packages ansible-packages configure-certs

install_docker: system-packages-docker configure-certs

clean_docker:
	@docker kill xopera  > /dev/null 2>&1 | true
	@docker rm xopera > /dev/null 2>&1 | true

build: clean
	@cd "${0%/*}"
	@docker build -t xopera_rest .
	@mkdir -p Builds/
	@docker save -o Builds/xopera_rest.tar xopera_rest

tests: clean_docker
	@echo "Starting test environment..."
	@sudo docker run -p 5000:5000 -v /root/.ssh/:/root/.ssh/ --name xopera -d xopera_rest > /dev/null 2>&1 | true
	@sleep 3
	@echo "Done."
	@echo "Running tests..."
	@pytest
	@docker kill xopera > /dev/null
	@docker rm xopera > /dev/null
	@echo "Done."

run_docker: clean_docker
	@echo "starting xOpera REST API from docker..."
	@sudo docker run -p 5000:5000 -v /root/.ssh/:/root/.ssh/ -v "$$PWD/Builds":/home/xopera/build/ -d --name xopera xopera_rest > /dev/null
	@echo "Done."
	@echo "Running on http://localhost:5000"
	@echo "To stop xopera, execute make clean_docker"


venv: venv/bin/activate
venv/bin/activate: requirements.txt
	test -d venv || virtualenv --python=python3.6 venv
	venv/bin/pip install -Ur requirements.txt
	touch venv/bin/activate
 
run: venv
	sudo Implementation/run.sh
	sudo python3 Implementation/run.py
	

all: clean install build tests run
all_docker: clean install_docker build tests run_docker


