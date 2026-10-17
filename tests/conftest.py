import pytest


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def dorm_client(client, settings):
    settings.DEBUG = True
    return client
