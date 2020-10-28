#!/usr/bin/env bash
#
# Build or push an image.
# Images for staging are pushed to sodalite-private-registry on ${docker_registry_ip}
# Images with production-ready version are pushed to both sodalite-private-registry and dockerhub: sodaliteh2020 repository

# Images from tagged commits are tagged with git tag
# Images from non-tagged commits are tagged with <last_git_tag>-<commits_since_tag>-<abbreviated_commit_sha>
#
# Usage:
#   $0 build <image-name> [Dockerfile-filename]
#   $0 push <image-name> [production|staging]
# image name is pure name without repository (image-name, not sodaliteh2020/image-name)

build() {
    set -x
    docker build --build-arg VERSION="${VERSION}" --build-arg DATE="${DATE}" -t "${IMAGE}":latest -f "${FILE}" .
    set +x
}

push() {

    set -x
    docker tag "${IMAGE}":latest "${TARGET_REGISTRY}/${IMAGE}:${VERSION}"
    docker tag "${IMAGE}":latest "${TARGET_REGISTRY}/${IMAGE}:latest"
    docker push "${TARGET_REGISTRY}/${IMAGE}:${VERSION}"
    docker push "${TARGET_REGISTRY}/${IMAGE}:latest"
    set +x
}


if [[ $# -gt 3 ]] || [[ $# -lt 2 ]] || \
   [[ "$1" != "build" && "$1" != "push" ]] || \
   [[ "$1" = "push" && "$3" != "staging" && "$3" != "production" ]]; then

    echo "Usage: $0 build <image-name> [Dockerfile-filename]"
    echo "Usage: $0 push <image-name> [production|staging]"
    exit 1
fi

git fetch --tags

ACTION=$1
IMAGE=$2
if [ "$ACTION" = 'build' ];
  then
    FILE=${3:-Dockerfile}
  else
    TARGET=${3:-staging}
fi

if [[ "$ACTION" = 'push' ]]; then
  if [[ "$TARGET" = 'production' ]]; then
    TARGET_REGISTRY=sodaliteh2020
  else
    TARGET_REGISTRY=${docker_registry_ip:-localhost}
  fi
fi

VERSION=$(git describe --tag --always | sed -e"s/^v//")
DATE=$(date -u +%Y-%m-%dT%H:%M:%S)

# debug section
echo "make_docker.sh:"
echo "ACTION: $ACTION"
echo "IMAGE: $IMAGE"
echo "FILE: $FILE"
echo "VERSION: $VERSION"
echo "DATE: $DATE"
echo "TARGET: $TARGET"
echo "TARGET_REGISTRY: $TARGET_REGISTRY"


if [ "$ACTION" = "build" ]; then
    build
else
    push
fi
