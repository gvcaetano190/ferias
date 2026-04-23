from django.urls import path

from apps.passwords.views import PasswordListCreateView, check_password_status, collaborator_lookup


urlpatterns = [
    path("", PasswordListCreateView.as_view(), name="index"),
    path("lookup/", collaborator_lookup, name="lookup"),
    path("<int:pk>/status/", check_password_status, name="status"),
]
