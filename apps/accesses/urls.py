from django.urls import path

from apps.accesses.views import index


urlpatterns = [
    path("", index, name="index"),
]

