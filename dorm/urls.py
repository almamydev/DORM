from django.urls import path

from . import views

app_name = "dorm"

urlpatterns = [
    path("", views.playground, name="playground"),
    path("run/", views.run_query, name="run"),
]
