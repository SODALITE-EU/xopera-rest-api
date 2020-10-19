#!/usr/bin/env bash
#
# Builds or push an image.
# Commits on branches (not master) are tagged with the branch name.
# Commits on master are tagged with latest and with the version number
#
# Usage:
#   $0 [build|push] <image-name> [Dockerfile-filename]

build() {
    # set -x
    docker build --build-arg VERSION="${VERSION}" --build-arg DATE="${DATE}" -t "${IMAGE}":latest -f "${FILE}" .
   # set +x
}

push() {
    # set -x
    docker tag "${IMAGE}":latest "${IMAGE}":"${VERSION}"
    docker push "${IMAGE}":"${VERSION}"
    docker push "${IMAGE}":latest
    # set +x
    # if [ "$BRANCH" = "master" ]; then
    #     set -x
    #     docker push ${IMAGE}:latest
    #     set +x
    # fi
}


if [ $# -gt 3 ] || [ $# -lt 2 ] || [[ "$1" != "build" && "$1" != "push" ]] ; then
    echo "Usage: $0 [build|push] <image-name> [Dockerfile-filename]"
    exit 1
fi

git fetch --tags

ACTION=$1
IMAGE=$2
FILE=${3:-Dockerfile}
VERSION=$(git describe --tag --always | sed -e"s/^v//")
DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
JENKINS_BRANCH=${CHANGE_BRANCH:-$GIT_BRANCH}
# Detect if under Jenkins; if not, use DEFAULT_BRANCH
BRANCH=${JENKINS_BRANCH:-$DEFAULT_BRANCH}

if [ "$BRANCH" != "master" ]; then
    VERSION="${VERSION}+${BRANCH}"

else
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Skipping untagged commit on master"
	#  exit 0
    fi
fi

# check Semantic versioning compliance
if [[ ! "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]]; then
        echo "SemVal failure"
	      # exit 0
fi

# debug section
echo "ACTION: $ACTION"
echo "IMAGE: $IMAGE"
echo "FILE: $FILE"
echo "VERSION: $VERSION"
echo "DATE: $DATE"
echo "DEFAULT_BRANCH: $DEFAULT_BRANCH"
echo "JENKINS_BRANCH: $JENKINS_BRANCH"
echo "BRANCH: $BRANCH"

exit 0


if [ "$ACTION" = "build" ]; then
    build
else
    push
fi
