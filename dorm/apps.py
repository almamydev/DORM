from django.apps import AppConfig


class DormConfig(AppConfig):
    name = "dorm"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import checks   # noqa: F401 — registers dorm.W001
        from . import storage  # noqa: F401 — connects the setting_changed receiver
