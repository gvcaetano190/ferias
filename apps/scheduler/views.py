from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.scheduler.services import SchedulerService


@login_required
def index(request):
    context = SchedulerService().dashboard_data()
    return render(request, "scheduler/index.html", context)


@login_required
def run_now(request, pk: int):
    if request.method != "POST":
        return redirect("scheduler:index")

    service = SchedulerService()
    job = service.repository.get_job(pk)
    if not job:
        messages.error(request, "Job não encontrado.")
        return redirect("scheduler:index")

    result = service.run_job(job)
    level = messages.success if result.status == "SUCCESS" else messages.error if result.status == "ERROR" else messages.warning
    level(request, f"{job.name}: {result.message}")
    return redirect("scheduler:index")


@login_required
def start_runtime(request):
    if request.method != "POST":
        return redirect("scheduler:index")

    ok, message = SchedulerService().start_runtime()
    (messages.success if ok else messages.warning)(request, message)
    return redirect("scheduler:index")


@login_required
def stop_runtime(request):
    if request.method != "POST":
        return redirect("scheduler:index")

    ok, message = SchedulerService().stop_runtime()
    (messages.success if ok else messages.warning)(request, message)
    return redirect("scheduler:index")


@login_required
def restart_runtime(request):
    if request.method != "POST":
        return redirect("scheduler:index")

    ok, message = SchedulerService().restart_runtime()
    (messages.success if ok else messages.warning)(request, message)
    return redirect("scheduler:index")
