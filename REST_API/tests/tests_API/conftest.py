# content of conftest.py
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--url", action="store", default='http://0.0.0.0:5000', help="url of REST api"
    )


@pytest.fixture
def url(request):
    return request.config.getoption("--url")
