from django.urls import path

from apps.scheduler.views import index, run_now


urlpatterns = [
    path("", index, name="index"),
    path("<int:pk>/run/", run_now, name="run_now"),
]

