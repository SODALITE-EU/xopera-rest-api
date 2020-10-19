#!/usr/bin/env bash
#
# Build or push an image.
# Images for staging are pushed to sodalite-private-registry on ${docker_registry_ip}
# Images with production-ready version are pushed to both sodalite-private-registry and dockerhub: sodaliteh2020 repository

# Images from tagged commits are tagged with git tag
# Images from non-tagged commits are tagged with <last_git_tag>-<commits_since_tag>-<abbreviated_commit_sha>
#
# Usage:
#   $0 [build|push] <image-name> [Dockerfile-filename]
# image name is pure name without repository (image-name, not sodaliteh2020/image-name)

build() {
    # set -x
    docker build --build-arg VERSION="${VERSION}" --build-arg DATE="${DATE}" -t "${IMAGE}":latest -f "${FILE}" .
   # set +x
}

push() {
    set -x
    docker tag "${IMAGE}":latest "${REGISTRY_IP}/${IMAGE}:${VERSION}"
    docker tag "${IMAGE}":latest "${REGISTRY_IP}/${IMAGE}:latest"
    docker push "${REGISTRY_IP}/${IMAGE}:${VERSION}"
    docker push "${REGISTRY_IP}/${IMAGE}:latest"
    set +x
    if [ "$PRODUCTION" = true ]; then

      set -x
      docker tag "${IMAGE}":latest sodaliteh2020/"${IMAGE}:${VERSION}"
      docker tag "${IMAGE}":latest sodaliteh2020/"${IMAGE}:latest"
      docker push sodaliteh2020/"${IMAGE}:${VERSION}"
      docker push sodaliteh2020/"${IMAGE}:latest"
      set +x
    fi
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
# Detect if under Jenkins; if not, use DEFAULT_REGISTRY
DEFAULT_REGISTRY=localhost
REGISTRY_IP=${docker_registry_ip:-$DEFAULT_REGISTRY}

# check Semantic versioning compliance
if [[ ! "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]]; then
        echo "Version does not comply with Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)"
	      exit 1
fi

# Check if production ready
if [[ "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
then
  PRODUCTION=true
else
  PRODUCTION=false
fi


# debug section
echo "ACTION: $ACTION"
echo "IMAGE: $IMAGE"
echo "FILE: $FILE"
echo "VERSION: $VERSION"
echo "DATE: $DATE"
echo "PRODUCTION: $PRODUCTION"


if [ "$ACTION" = "build" ]; then
    build
else
    push
fi
