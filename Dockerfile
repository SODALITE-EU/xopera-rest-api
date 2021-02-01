FROM openjdk:11.0.8-jre-buster as builder
WORKDIR /build/
COPY . /build/
RUN /build/generate.sh


FROM python:3.8.7-alpine3.12
WORKDIR /app
ENTRYPOINT ["python3"]
CMD ["-m", "opera.api.cli"]

COPY requirements.txt requirements.yml /app/

ARG HELM_VERSION=3.4.0
ARG KUBECTL_VERSION=1.20.0
ENV BASE_URL=https://get.helm.sh
ENV TAR_FILE=helm-v${HELM_VERSION}-linux-amd64.tar.gz

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

RUN export BUILD_PREREQS="gcc musl-dev libffi-dev openssl-dev python3-dev postgresql-dev" \
    && export PACKAGES="git bash openssh-client libpq" \
    && apk add --no-cache $PACKAGES $BUILD_PREREQS \
    && pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir -r requirements.txt \
    && ansible-galaxy install -r requirements.yml \
    && apk del $BUILD_PREREQS \
    && rm requirements.txt requirements.yml

COPY --from=builder /build/src/ /app/
