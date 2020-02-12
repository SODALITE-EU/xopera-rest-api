#####################################################
#################     START BIG     #################
#####################################################

FROM alpine:3.10 as big

RUN echo "**** install Python ****" && \
    apk add --no-cache python3 && \
    if [ ! -e /usr/bin/python ]; then ln -sf python3 /usr/bin/python ; fi && \
    \
    echo "**** install pip ****" && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --no-cache --upgrade pip setuptools wheel && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi

# Install build prerequisites and build
RUN apk update && \
    apk add py-virtualenv gcc python3-dev musl-dev linux-headers libffi-dev libressl-dev postgresql-dev bash openssh-client && \
    pip install -U wheel "opera[openstack]<0.5" flask flask_restplus psycopg2 jinja2 docker-py "Werkzeug<1"

RUN pip wheel --wheel-dir=/root/wheels wheel "opera[openstack]<0.5" flask psycopg2 jinja2 docker-py "Werkzeug<1"

#####################################################
#################   MAKE IT SMALL   #################
#####################################################

FROM alpine:3.10 as small

# Install prerequisites
RUN echo "**** install Python ****" && \
    apk add --no-cache python3 && \
    if [ ! -e /usr/bin/python ]; then ln -sf python3 /usr/bin/python ; fi && \
    \
    echo "**** install pip ****" && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --no-cache --upgrade pip setuptools wheel && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi

RUN apk update && \
    apk add --no-cache musl-dev libffi-dev libressl-dev postgresql-dev bash openssh-client ca-certificates

# Copy from big image
COPY --from=big /root/wheels /root/wheels
RUN pip install --find-links=/root/wheels wheel "opera[openstack]<0.5" flask flask_restplus psycopg2 jinja2 docker-py "Werkzeug<1"

# Install required ansible libraries
RUN ansible-galaxy install geerlingguy.docker && \
    ansible-galaxy install geerlingguy.pip && \
    ansible-galaxy install geerlingguy.repo-epel

# Copy required certificates and install them
COPY Certs/ca.crt /home/xopera/certs/ca.crt
COPY Certs/ca.key /home/xopera/certs/ca.key
COPY Certs/firstdeploy/*.crt /home/xopera/certs/xopera.local.crt
COPY Certs/firstdeploy/*.key /home/xopera/certs/xopera.local.key
COPY Certs/ca.crt /usr/local/share/ca-certificates/ca.crt
RUN update-ca-certificates

# copy OpenStack keys
# COPY Certs/os_keys /root/.ssh

# create OpenStack key
# WORKDIR /root/.ssh
# RUN ssh-keygen -t rsa -f xOpera_os.key

# Install xOpera REST API
COPY Implementation /usr/local/xopera_rest
WORKDIR /usr/local/xopera_rest

# Start xOpera REST API on startup
ENTRYPOINT ["python"]
CMD ["run.py"]

# ENTRYPOINT cd /usr/local/xopera_rest/ && pwd && ./run.sh
EXPOSE 5000