import pytest
from django.apps import apps
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.checks import run_checks
from django.core.management import call_command
from django.urls import reverse

URLS = ["dorm:playground", "dorm:history"]


@pytest.fixture
def prod(settings):
    """DEBUG=False with every required DORM setting in place."""
    settings.DEBUG = False
    settings.DORM_URL_NAME = "secret-orm"
    settings.DORM_AUTH_ACCESS = True
    settings.DORM_PERMISSION_ACCESS = True
    return settings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dev", password="pass")


@pytest.fixture
def dorm_permission(db):
    """What a project does: attach the permission to its user model."""
    return Permission.objects.create(
        codename="can_access_dorm_plg",
        name="Can access the DORM playground",
        content_type=ContentType.objects.get_for_model(User),
    )


@pytest.fixture
def perm_user(dorm_permission):
    granted = User.objects.create_user(username="granted", password="pass")
    granted.user_permissions.add(dorm_permission)
    return granted


def _status(client, name="dorm:playground"):
    return client.get(reverse(name)).status_code


# --- DEBUG=False ---

@pytest.mark.django_db
@pytest.mark.parametrize("name", URLS)
def test_prod_user_with_permission(client, prod, perm_user, name):
    client.force_login(perm_user)
    assert _status(client, name) == 200


@pytest.mark.django_db
def test_prod_superuser_passes_without_explicit_permission(client, prod):
    client.force_login(User.objects.create_superuser("root", "r@x.io", "pass"))
    assert _status(client) == 200


@pytest.mark.django_db
def test_prod_user_without_permission(client, prod, user):
    client.force_login(user)
    assert _status(client) == 404


@pytest.mark.django_db
def test_prod_anonymous(client, prod):
    assert _status(client) == 404


@pytest.mark.django_db
@pytest.mark.parametrize("override", [
    {"DORM_URL_NAME": "__dorm__"},
    {"DORM_URL_NAME": ""},
    {"DORM_AUTH_ACCESS": False},
    {"DORM_PERMISSION_ACCESS": False},
])
def test_prod_missing_setting_is_404_even_for_superuser(client, prod, override):
    for key, value in override.items():
        setattr(prod, key, value)
    client.force_login(User.objects.create_superuser("root", "r@x.io", "pass"))
    assert _status(client) == 404


@pytest.mark.django_db
def test_prod_unset_url_name_is_404(client, prod):
    del prod.DORM_URL_NAME
    client.force_login(User.objects.create_superuser("root", "r@x.io", "pass"))
    assert _status(client) == 404


@pytest.mark.django_db
def test_prod_post_endpoints_follow_same_rules(client, prod, user, perm_user):
    client.force_login(user)
    assert client.post(reverse("dorm:run"), {"code": "1"}).status_code == 404
    client.force_login(perm_user)
    assert client.post(reverse("dorm:run"), {"code": "1"}).status_code == 200


@pytest.mark.django_db
def test_custom_permission_name(client, prod, user):
    prod.DORM_PERMISSION_NAME = "auth.view_user"
    user.user_permissions.add(Permission.objects.get(codename="view_user"))
    client.force_login(user)
    assert _status(client) == 200


@pytest.mark.django_db
def test_dotted_permission_name_must_match_app(client, prod, perm_user):
    prod.DORM_PERMISSION_NAME = "library.can_access_dorm_plg"   # granted perm is auth.*
    client.force_login(perm_user)
    assert _status(client) == 404
    prod.DORM_PERMISSION_NAME = "auth.can_access_dorm_plg"
    assert _status(client) == 200


@pytest.mark.django_db
def test_inactive_superuser_is_denied(client, prod):
    root = User.objects.create_superuser("root", "r@x.io", "pass")
    root.is_active = False
    root.save()
    client.force_login(root)
    assert _status(client) == 404


# --- DEBUG=True ---

@pytest.mark.django_db
def test_debug_permission_access_requires_permission(client, settings, user, perm_user):
    settings.DEBUG = True
    settings.DORM_PERMISSION_ACCESS = True
    assert _status(client) == 404
    client.force_login(user)
    assert _status(client) == 404
    client.force_login(perm_user)
    assert _status(client) == 200


@pytest.mark.django_db
def test_debug_default_url_name_is_fine(dorm_client, settings):
    settings.DORM_URL_NAME = "__dorm__"
    assert _status(dorm_client) == 200


# --- system check ---

def test_check_warns_when_prod_misconfigured(settings):
    settings.DEBUG = False
    settings.DORM_AUTH_ACCESS = False
    ids = [m.id for m in run_checks()]
    assert "dorm.W001" in ids


def test_check_silent_when_prod_configured(prod):
    assert "dorm.W001" not in [m.id for m in run_checks()]


def test_check_silent_in_debug(settings):
    settings.DEBUG = True
    assert "dorm.W001" not in [m.id for m in run_checks()]


# --- DORM ships no models ---

def test_dorm_registers_no_models():
    assert list(apps.get_app_config("dorm").get_models()) == []


@pytest.mark.django_db
def test_dorm_needs_no_migrations():
    call_command("makemigrations", "dorm", "--check", "--dry-run", verbosity=0)
