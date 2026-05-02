__version__ = "0.1.0"


def get_url_prefix() -> str:
    """Return the URL prefix for DORM, read from settings.DORM_URL (default: '__dorm__')."""
    from django.conf import settings
    return getattr(settings, "DORM_URL_NAME", "__dorm__")
