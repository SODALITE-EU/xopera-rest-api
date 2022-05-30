FROM openjdk:11.0.8-jre-buster as app-builder
WORKDIR /build/
COPY . /build/
RUN /build/generate.sh


FROM python:3.10-alpine3.13 as python-builder
COPY requirements.txt .
RUN export BUILD_PREREQS="gcc musl-dev libffi-dev openssl-dev postgresql-dev cargo" \
    && apk add --no-cache $BUILD_PREREQS \
    && pip3 install --no-cache-dir wheel \
    && pip3 install --user --no-warn-script-location -r requirements.txt

FROM python:3.10.4-alpine3.15

ARG HELM_VERSION=3.5.3
ARG KUBECTL_VERSION=1.20.4
ARG PYTHON_LIB_VERSION=3.10
ENV BASE_URL=https://get.helm.sh
ENV TAR_FILE=helm-v${HELM_VERSION}-linux-amd64.tar.gz

# install system-packages
RUN export PACKAGES="git bash openssh-client libpq" \
    && apk add --no-cache $PACKAGES

# copy python packages
COPY --from=python-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python${PYTHON_LIB_VERSION}/site-packages

# install kubectl
RUN apk add --update --no-cache curl \
    && curl -LO https://storage.googleapis.com/kubernetes-release/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl \
    && mv kubectl /usr/bin/kubectl \
    && chmod +x /usr/bin/kubectl \
    && apk del curl \
    && rm -f /var/cache/apk/*

# install helm
RUN apk add --update --no-cache curl ca-certificates bash git \
    && curl -L ${BASE_URL}/${TAR_FILE} |tar xvz \
    && mv linux-amd64/helm /usr/bin/helm \
    && chmod +x /usr/bin/helm \
    && rm -rf linux-amd64 \
    && apk del curl \
    && rm -f /var/cache/apk/*

# install ansible roles and collections
COPY requirements.yml .
RUN ansible-galaxy install -r requirements.yml \
    && rm requirements.yml

# temporary fix for pre release opera
RUN pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ opera==0.6.9.dev2

# grant access to all users for root bin and lib
RUN chmod 755 /root
RUN chmod 755 $PYTHONPATH
ENV XOPERA_API_WORKDIR=/app/.xopera-api
ENV ANSIBLE_ROLES_PATH=/root/.ansible/roles:$ANSIBLE_ROLES_PATH

# copy app code
COPY --from=app-builder /build/src/ /app/
COPY openapi-spec.yml /app/

WORKDIR /app
ENTRYPOINT ["python3"]
CMD ["-m", "opera.api.cli"]
