from django.contrib import admin
from django.urls import include, path

from dorm import get_url_prefix

urlpatterns = [
    path("admin/", admin.site.urls),
    path(f"{get_url_prefix()}/", include("dorm.urls", namespace="dorm")),
]
