FROM openjdk:11.0.8-jre-buster as builder
WORKDIR /build/
COPY . /build/
RUN /build/generate.sh


FROM python:3.8.6-alpine3.12
WORKDIR /app
ENTRYPOINT ["python3"]
CMD ["-m", "opera.api.cli"]

COPY requirements.txt requirements.yml /app/

RUN export BUILD_PREREQS="gcc musl-dev libffi-dev openssl-dev python3-dev postgresql-dev" \
    && export PACKAGES="git bash openssh-client libpq" \
    && apk add --no-cache $PACKAGES $BUILD_PREREQS \
    && pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir -r requirements.txt \
    && ansible-galaxy install -r requirements.yml \
    && apk del $BUILD_PREREQS \
    && rm requirements.txt requirements.yml

COPY --from=builder /build/src/ /app/
