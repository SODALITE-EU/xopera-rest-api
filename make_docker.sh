#!/usr/bin/env bash

# make_docker V2
#
# Build or push an image.

# Images from non-tagged commits are versioned by <last_git_tag>-<commits_since_tag>-<abbreviated_commit_sha>
# Images from tagged commits are versioned by git tag

# Images for staging are tagged and pushed only with ${VERSION}
# Images for production are tagged and pushed with both tags: latest and ${VERSION}

#
# Usage:
#   $0 build <image-name> [Dockerfile-filename]
#   $0 push <image-name> <target-registry> [production|staging]
# image name is pure name without repository (image-name, not sodaliteh2020/image-name)

build() {
    set -x
    docker build --build-arg VERSION="${VERSION}" --build-arg DATE="${DATE}" -t "${IMAGE}":latest -f "${FILE}" .
    set +x
}

push() {
    set -x
    docker tag "${IMAGE}":latest "${TARGET_REGISTRY}/${IMAGE}:${VERSION}"
    docker push "${TARGET_REGISTRY}/${IMAGE}:${VERSION}"
    set +x

    if [[ "$TARGET" = 'production' ]]; then
      set -x
      docker tag "${IMAGE}":latest "${TARGET_REGISTRY}/${IMAGE}:latest"
      docker push "${TARGET_REGISTRY}/${IMAGE}:latest"
      set +x
    fi

}


if [[ "$1" != "build" && "$1" != "push" ]] || \
   [[ "$1" = "build" ]] && [[ $# -gt 3 || $# -lt 2 ]] || \
   [[ "$1" = "push" ]] && [[ $# -gt 4 || $# -lt 3 ]] && [[ "$4" != "staging" && "$4" != "production" ]]; then

    echo "Usage: $0 build <image-name> [Dockerfile-filename]"
    echo "Usage: $0 push <image-name> <target-registry> [production|staging]"
    exit 1
fi

git fetch --tags -f
ACTION=$1
IMAGE=$2
if [ "$ACTION" = 'build' ];
  then
    FILE=${3:-Dockerfile}
  else
    TARGET_REGISTRY=$3
    TARGET=${4:-staging}
fi

VERSION=$(git describe --tag --always | sed -e"s/^v//")
DATE=$(date -u +%Y-%m-%dT%H:%M:%S)

# debug section
echo "make_docker.sh:"
echo
echo "---------------"
echo "ACTION: $ACTION"
if [ "$ACTION" = 'push' ]; then
  echo "TARGET: $TARGET"
  echo "TARGET_REGISTRY: $TARGET_REGISTRY"
fi
echo "IMAGE: $IMAGE"
if [ "$ACTION" = 'build' ]; then
  echo "FILE: $FILE"
fi
echo "VERSION: $VERSION"
echo "DATE: $DATE"

echo "---------------"
echo

if [ "$ACTION" = "build" ]; then
    build
else
    push
fi

echo