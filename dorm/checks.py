from django.conf import settings
from django.core.checks import Warning, register

from .access import production_issues


@register()
def check_production_access(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    issues = production_issues()
    if not issues:
        return []
    return [Warning(
        "DORM is installed with DEBUG=False but is not configured for it, "
        "so every DORM URL returns 404.",
        hint="; ".join(issues) + ". Or remove 'dorm' from INSTALLED_APPS.",
        id="dorm.W001",
    )]
