from django.apps import AppConfig


class DormConfig(AppConfig):
    name = "dorm"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import logging
        from django.conf import settings

        if not settings.DEBUG:
            logging.getLogger("dorm").warning(
                "DORM is installed but DEBUG=False — all requests will return 404. "
                "Consider removing 'dorm' from INSTALLED_APPS in production."
            )
