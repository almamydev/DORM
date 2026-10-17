__version__ = "0.2.0"

DEFAULT_URL_NAME = "__dorm__"


def get_url_prefix() -> str:
    """Return the URL prefix for DORM, read from settings.DORM_URL_NAME (default: '__dorm__')."""
    from django.conf import settings
    return getattr(settings, "DORM_URL_NAME", DEFAULT_URL_NAME)
