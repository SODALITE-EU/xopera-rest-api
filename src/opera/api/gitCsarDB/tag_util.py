def decode_tag(tag: str):
    """
    transform tag: str to tag: tuple
    'v1.1' -> (1,1)
    'v1' -> (1,0)
    """
    tag_parsed = tag[1:].split('.')
    if len(tag_parsed) == 1:
        tag_parsed.append('0')
    return int(tag_parsed[0]), int(tag_parsed[1])


def encode_tag(tag: tuple):
    """
    converts tag back to string
    (1,1) -> 'v1.1'
    (1,0) -> 'v1.0'
    """
    return f'v{tag[0]}.{tag[1]}'


def parse_tags(tags):
    """
    transforms list of tags (in string format or git.refs.tag.TagReference) to sorted list of tuples
    """

    tags_str = [str(tag) for tag in tags]
    tags_parsed = [decode_tag(tag) for tag in tags_str]
    tags_sorted = sorted(tags_parsed, key=lambda x: (x[0], x[1]))
    return tags_sorted


def next_major(tags: list, return_tuple=False):
    """
    returns next tag: tuple or str with incremented major version
    """
    tags_tuples = parse_tags(tags)
    tags_sorted = sorted(tags_tuples, key=lambda x: (x[0], x[1]))
    if not tags_sorted:
        next_tag_tuple = 1, 0
    else:
        next_tag_tuple = tags_sorted[-1][0] + 1, 0

    if return_tuple:
        return next_tag_tuple

    return encode_tag(next_tag_tuple)


def next_minor(tags: list, tag: str, return_tuple=False):
    """
    returns next tag: tuple or str with incremented minor version, relative to tag
    """
    tags_tuples = parse_tags(tags)
    tag_chosen = decode_tag(tag)
    if not tags_tuples:
        next_tag_tuple = 1, 0
    elif tag_chosen not in tags_tuples:
        next_tag_tuple = tag_chosen
    else:
        minor_versions = sorted([int(tag_tuple[1]) for tag_tuple in tags_tuples if tag_tuple[0] == tag_chosen[0]])
        next_tag_tuple = tag_chosen[0], max(minor_versions) + 1

    if return_tuple:
        return next_tag_tuple

    return encode_tag(next_tag_tuple)
