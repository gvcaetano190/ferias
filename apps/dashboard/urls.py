from django.urls import path

from apps.dashboard.views import home


urlpatterns = [
    path("", home, name="home"),
]
