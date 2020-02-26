#!/bin/bash
registry_ip="$1"
tag="$2"

if [[ -z "$registry_ip" || "$1" == "-h" ]]; then
  echo "Build, tag and push docker images to docker registry."
  echo "Usage: ./$(basename "$0") [registry_ip] [(optional) image_tag]"
  exit
fi

components=(
  'flask'
  'nginx'
)

for component in "${components[@]}"; do
    image_tag=xopera-"$component"
    if [[ -n "$tag" ]]; then
        image_tag="$image_tag":"$tag"
    fi
    docker build -t "$image_tag" -f Dockerfile-"$component" . || exit
    docker tag "$image_tag" "$registry_ip"/"$image_tag"
    docker push "$registry_ip"/"$image_tag" || exit
done

echo Done
