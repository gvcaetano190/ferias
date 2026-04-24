from django.urls import path

from apps.scheduler.views import index, restart_runtime, run_now, start_runtime, stop_runtime


urlpatterns = [
    path("", index, name="index"),
    path("runtime/start/", start_runtime, name="start_runtime"),
    path("runtime/stop/", stop_runtime, name="stop_runtime"),
    path("runtime/restart/", restart_runtime, name="restart_runtime"),
    path("<int:pk>/run/", run_now, name="run_now"),
]
