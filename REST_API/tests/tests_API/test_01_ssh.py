import ipaddress
import os
import re
import subprocess

import requests
from assertpy import assert_that, fail


class TestSSH:

    def test_connection(self, url):
        resp = requests.get(url=url + "/ssh/keys/public")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()).is_not_none()

    def test_dict_keys(self, url):
        resp = requests.get(url=url + "/ssh/keys/public")
        assert_that(resp.json()).contains_only("key_pair_name", "public_key")

    def test_key_name(self, url):
        resp = requests.get(url=url + "/ssh/keys/public")
        key_pair_name = resp.json()["key_pair_name"]
        assert_that(key_pair_name).ends_with('xOpera')
        assert_that(key_pair_name).matches(r"\d{1,3}\-\d{1,3}\-\d{1,3}\-\d{1,3}")

    def test_valid_ip(self, url):
        resp = requests.get(url=url + "/ssh/keys/public")
        key_pair_name = resp.json()["key_pair_name"]
        try:
            ip = re.search(r"\d{1,3}\-\d{1,3}\-\d{1,3}\-\d{1,3}", key_pair_name).group().replace('-', '.')
            ipaddress.IPv4Address(ip)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            fail("key_pair_name does not contain valid IP address: " + str(e))

    def test_public_key(self, url):
        resp = requests.get(url=url + "/ssh/keys/public")
        key = resp.json()["public_key"]

        path = 'id_rsa.pub'
        with open(path, 'w') as key_file:
            key_file.write(key)
        ssh_keygen_response = subprocess.check_output("ssh-keygen -l -f {}".format(path), shell=True).decode('utf-8')
        os.remove(path)

        assert_that(ssh_keygen_response).does_not_contain("is not a public key")
        ssh_key_properties = ssh_keygen_response.strip().split(" ")

        algorithm = ssh_key_properties[-1].strip("()")
        assert_that(algorithm).is_equal_to("RSA")

        key_size = int(ssh_key_properties[0])
        assert_that(key_size).is_greater_than_or_equal_to(2048)
        # assert_that(key_size).is_greater_than_or_equal_to(4096)


if __name__ == '__main__':
    test = TestSSH()
    test.test_public_key(url="http://localhost:5000")
