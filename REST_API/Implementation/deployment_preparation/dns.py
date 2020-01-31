import re

DNS_LABEL_MAX_LEN = 63
DNS_LABEL_REGEX = "[a-z0-9-]{1,%d}$" % DNS_LABEL_MAX_LEN
FQDN_MAX_LEN = 255


def _validate_dns_format(data, max_len=FQDN_MAX_LEN):
    # NOTE: An individual name regex instead of an entire FQDN was used
    # because its easier to make correct. The logic should validate that the
    # dns_name matches RFC 1123 (section 2.1) and RFC 952.
    if not data:
        return
    try:
        # Trailing periods are allowed to indicate that a name is fully
        # qualified per RFC 1034 (page 7).
        trimmed = data if not data.endswith('.') else data[:-1]
        if len(trimmed) > 255:
            raise TypeError(
                "'%s' exceeds the 255 character FQDN limit" % trimmed)
        names = trimmed.split('.')
        for name in names:
            if not name:
                raise TypeError("Encountered an empty component.")
            if name.endswith('-') or name[0] == '-':
                raise TypeError(
                    "Name '%s' must not start or end with a hyphen." % name)
            # TODO what to do with exception like this?
            # if not re.match(DNS_LABEL_REGEX, name):
            #     raise TypeError(
            #          ("Name '%s' must be 1-63 characters long, each of "
            #          "which can only be alphanumeric or a hyphen.") % name)
        # RFC 1123 hints that a TLD can't be all numeric. last is a TLD if
        # it's an FQDN.
        if len(names) > 1 and re.match("^[0-9]+$", names[-1]):
            raise TypeError("TLD '%s' must not be all numeric" % names[-1])
        # print('ok')
    except TypeError as e:
        msg = "'%(data)s' not a valid PQDN or FQDN. Reason: %(reason)s" % {
            'data': data, 'reason': str(e)}
        return msg


if __name__ == '__main__':
    print(_validate_dns_format(data='a_{}'))
