cd "${0%/*}" || exit
docker build -t xopera_rest .
mkdir -p Builds/
docker save -o Builds/xopera_rest.tar xopera_rest