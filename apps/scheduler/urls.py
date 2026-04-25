from django.urls import path

from apps.scheduler.views import force_stop_execution, force_stop_modal, index, restart_runtime, run_now, start_runtime, stop_runtime


urlpatterns = [
    path("", index, name="index"),
    path("runtime/start/", start_runtime, name="start_runtime"),
    path("runtime/stop/", stop_runtime, name="stop_runtime"),
    path("runtime/restart/", restart_runtime, name="restart_runtime"),
    path("runtime/force-stop/", force_stop_modal, name="force_stop_modal"),
    path("runtime/force-stop/<int:execution_id>/", force_stop_execution, name="force_stop_execution"),
    path("<int:pk>/run/", run_now, name="run_now"),
]
