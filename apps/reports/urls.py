from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("print/", views.dashboard_print, name="dashboard_print"),
]
