from assertpy import assert_that

from opera.api.gitCsarDB import tag_util


def test_encode_tag():
    assert_that(tag_util.encode_tag((1, 0))).is_equal_to('v1.0')
    assert_that(tag_util.encode_tag((5, 2))).is_equal_to('v5.2')


def test_decode_tag():
    assert_that(tag_util.decode_tag('v1.1')).is_equal_to((1, 1))
    assert_that(tag_util.decode_tag('v1')).is_equal_to((1, 0))
    assert_that(tag_util.decode_tag('v1.42')).is_equal_to((1, 42))


def test_parse_tags():
    tags = ['v5.1', 'v3.2', 'v3.1', 'v5.2', 'v1', 'v1.1']
    expected = [(1, 0), (1, 1), (3, 1), (3, 2), (5, 1), (5, 2)]
    assert_that(tag_util.parse_tags(tags)).is_equal_to(expected)


def test_next_major():
    assert_that(tag_util.next_major([])).is_equal_to('v1.0')
    tags = ['v5.1', 'v3.2', 'v3.1', 'v5.2', 'v1', 'v1.1']
    assert_that(tag_util.next_major(tags)).is_equal_to('v6.0')
    assert_that(tag_util.next_major(tags, return_tuple=True)).is_equal_to((6, 0))


def test_next_minor():
    assert_that(tag_util.next_minor([], 'v5.1')).is_equal_to('v1.0')
    tags = ['v5.1', 'v3.2', 'v3.1', 'v5.2', 'v1', 'v1.1']
    assert_that(tag_util.next_minor(tags, 'v5.1')).is_equal_to('v5.3')
    assert_that(tag_util.next_minor(tags, 'v5.2')).is_equal_to('v5.3')
    assert_that(tag_util.next_minor(tags, 'v42')).is_equal_to('v42.0')
    assert_that(tag_util.next_minor(tags, 'v5.1', return_tuple=True)).is_equal_to((5, 3))
