from django.urls import path

from apps.sync.views import trigger_sync


urlpatterns = [
    path("run/", trigger_sync, name="run"),
]
