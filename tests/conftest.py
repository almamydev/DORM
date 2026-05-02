import pytest


@pytest.fixture
def dorm_client(client, settings):
    settings.DEBUG = True
    return client
