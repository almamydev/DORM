import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_playground_accessible_in_debug(dorm_client):
    response = dorm_client.get(reverse("dorm:playground"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_playground_404_when_not_debug(client, settings):
    settings.DEBUG = False
    response = client.get(reverse("dorm:playground"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_playground_404_for_anonymous_when_auth_required(client, settings):
    settings.DEBUG = True
    settings.DORM_AUTH_ACCESS = True
    response = client.get(reverse("dorm:playground"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_playground_200_for_authenticated_when_auth_required(client, settings):
    settings.DEBUG = True
    settings.DORM_AUTH_ACCESS = True
    user = User.objects.create_user(username="dev", password="pass")
    client.force_login(user)
    response = client.get(reverse("dorm:playground"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_playground_200_without_auth_setting(dorm_client):
    """DORM_AUTH_ACCESS not set — anonymous access allowed in DEBUG mode."""
    response = dorm_client.get(reverse("dorm:playground"))
    assert response.status_code == 200
