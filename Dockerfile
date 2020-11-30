FROM openjdk:11.0.8-jre-buster as builder
WORKDIR /build/
COPY . /build/
RUN /build/generate.sh


FROM python:3.8.6-alpine3.12
WORKDIR /app
ENTRYPOINT ["python3"]
CMD ["-m", "opera.api.cli"]

COPY requirements.txt /app/

RUN export CRYPTOGRAPHY_PREREQS="gcc musl-dev libffi-dev openssl-dev python3-dev" \
    && export PIP_PREREQS="git postgresql-dev bash openssh-client" \
    && apk add $CRYPTOGRAPHY_PREREQS $PIP_PREREQS \
    && pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apk del $CRYPTOGRAPHY_PREREQS \
    && rm requirements.txt

COPY --from=builder /build/src/ /app/
