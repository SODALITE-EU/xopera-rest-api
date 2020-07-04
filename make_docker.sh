#!/usr/bin/env bash
#
# Builds or push an image.
# Commits on branches (not master) are tagged with the branch name.
# Commits on master are tagged with latest and with the version number
#
# Usage:
#   $0 [build|push] <image-name> [Dockerfile-filename]

build() {
    set -x
    docker build --build-arg VERSION=${VERSION} --build-arg DATE=${DATE} -t ${IMAGE}:latest -f ${FILE} .
    set +x
}

push() {
    set -x
    docker tag ${IMAGE}:latest ${IMAGE}:${VERSION}
    docker push ${IMAGE}:${VERSION}
    set +x
    if [ "$BRANCH" = "master" ]; then
        set -x
        docker push ${IMAGE}:latest
        set +x
    fi
}


if [ $# -gt 3 ] || [ $# -lt 2 ] || [[ "$1" != "build" && "$1" != "push" ]] ; then
    echo "Usage: $0 [build|push] <image-name> [Dockerfile-filename]"
    exit 1
fi

ACTION=$1
IMAGE=$2
FILE=${3:-Dockerfile}
VERSION=$(git describe --always --dirty | sed -e"s/^v//")
DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
JENKINS_BRANCH=${CHANGE_BRANCH:-$GIT_BRANCH}
# Detect if under Jenkins; if not, use DEFAULT_BRANCH
BRANCH=${JENKINS_BRANCH:-$DEFAULT_BRANCH}

if [ "$BRANCH" != "master" ]; then
    VERSION=$(echo $BRANCH | sed -e"s|/|-|")

else
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Skipping untagged commit on master"
	exit 0
    fi
fi


if [ "$ACTION" = "build" ]; then
    build
else
    push
fi
