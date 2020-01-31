cd "${0%/*}" || exit
docker build -t xopera_rest .
mkdir -p Builds/
docker save -o Builds/xopera_rest.tar xopera_rest

docker run -e DATABASE_IP=172.17.0.2 -p 5000:5000 -v "$PWD/Builds":/home/xopera/build/ -v /root/.ssh/:/root/.ssh/ -it xopera_rest