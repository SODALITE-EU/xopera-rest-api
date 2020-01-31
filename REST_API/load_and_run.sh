tar_path="$1"
registry_ip="$2"
database_ip="$3"

docker kill xopera
docker rm xopera
docker load --input "$tar_path"

docker run \
      --restart unless-stopped \
      -p 5000:5000 \
      -v "$PWD/Builds:/home/xopera/build/" \
      -v "/home/xopera/drive:/var/lib/xopera" \
      -v "/home/xopera/certs:/home/xopera/certs" \
      -v "/root/.ssh/:/root/.ssh/" \
      -v "/etc/docker/certs.d/$registry_ip:/etc/docker/certs.d/$registry_ip" \
      -e "DATABASE_IP=$database_ip" \
      -d --name xopera \
      xopera_rest

docker cp openrc.sh xopera:/usr/local/xopera_rest/settings/openrc.sh





