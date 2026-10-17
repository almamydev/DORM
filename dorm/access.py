"""
Who may open the DORM playground.

DEBUG=True
  - DORM_AUTH_ACCESS=True       → user must be authenticated
  - DORM_PERMISSION_ACCESS=True → user must hold DORM_PERMISSION_NAME
  - neither                     → open
DEBUG=False (all mandatory, otherwise 404)
  - DORM_URL_NAME set to something other than "__dorm__"
  - DORM_AUTH_ACCESS=True and DORM_PERMISSION_ACCESS=True
  - authenticated user holding DORM_PERMISSION_NAME

Active superusers always hold the permission.

DORM defines no models, so the permission is created by the project on one of
its own models (typically the user model). DORM_PERMISSION_NAME may be a bare
codename, matched on any app, or an exact "app_label.codename".
"""
from django.conf import settings

from . import DEFAULT_URL_NAME

DEFAULT_PERMISSION_NAME = "can_access_dorm_plg"


def permission_name() -> str:
    return getattr(settings, "DORM_PERMISSION_NAME", "") or DEFAULT_PERMISSION_NAME


def production_issues() -> list[str]:
    """Settings missing for DORM to be reachable with DEBUG=False (empty = ready)."""
    issues = []
    if getattr(settings, "DORM_URL_NAME", DEFAULT_URL_NAME) in ("", DEFAULT_URL_NAME):
        issues.append(f"DORM_URL_NAME must be set to a custom value (not {DEFAULT_URL_NAME!r})")
    if not getattr(settings, "DORM_AUTH_ACCESS", False):
        issues.append("DORM_AUTH_ACCESS must be True")
    if not getattr(settings, "DORM_PERMISSION_ACCESS", False):
        issues.append("DORM_PERMISSION_ACCESS must be True")
    return issues


def has_dorm_permission(user) -> bool:
    if not (user.is_authenticated and user.is_active):
        return False
    if user.is_superuser:
        return True
    name = permission_name()
    if "." in name:
        return user.has_perm(name)
    return any(perm.split(".", 1)[1] == name for perm in user.get_all_permissions())


def is_accessible(request) -> bool:
    user = getattr(request, "user", None)

    if settings.DEBUG:
        needs_auth = getattr(settings, "DORM_AUTH_ACCESS", False)
        needs_perm = getattr(settings, "DORM_PERMISSION_ACCESS", False)
        if not (needs_auth or needs_perm):
            return True
        if user is None or not user.is_authenticated:
            return False
        return not needs_perm or has_dorm_permission(user)

    if production_issues():
        return False
    return user is not None and has_dorm_permission(user)
