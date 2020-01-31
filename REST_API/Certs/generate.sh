rm -f ca.key
rm -f ca.crt
openssl req -newkey rsa:4096 -nodes -sha256 -keyout ca.key -x509 -days 800 -out ca.crt
chmod 644 ca.key
chmod 644 ca.crt