from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from console.models import SiteSettings
from jobs.forms import get_disabled_runners
from jobs.models import Job
from jobs.services import cancel_job, create_and_submit_job, hide_job, read_log_tail
from jobs.views.shared import _fallback_output_context, _job_queryset_for
from model_types import (
    get_model_type,
    get_model_types_by_category,
    get_submittable_model_types,
)


@login_required
def job_list(request):
    jobs = _job_queryset_for(request.user)

    # Search
    search = request.GET.get("search", "").strip()
    if search:
        jobs = jobs.filter(
            Q(id__icontains=search) | Q(name__icontains=search)
        ).distinct()

    # Filter by status
    status = request.GET.get("status", "")
    if status and status in [s.value for s in Job.Status]:
        jobs = jobs.filter(status=status)

    # Filter by runner
    runner = request.GET.get("runner", "")
    if runner:
        jobs = jobs.filter(runner=runner)

    # Unique runners for the dropdown
    runners = (
        Job.objects.filter(owner=request.user, hidden_from_owner=False)
        .values_list("runner", flat=True)
        .distinct()
    )

    jobs = jobs.order_by("-created_at")[:200]

    context = {
        "jobs": jobs,
        "search": search,
        "status": status,
        "runner": runner,
        "runners": runners,
        "statuses": Job.Status.choices,
    }
    return render(request, "jobs/list.html", context)


@login_required
def job_submit(request):
    site_settings = SiteSettings.get_settings()
    maintenance_mode = site_settings.maintenance_mode
    maintenance_message = site_settings.maintenance_message
    disabled_runners = get_disabled_runners()
    model_key = request.GET.get("model") or request.POST.get("model")

    if not model_key and request.method == "GET":
        return render(
            request,
            "jobs/select_model.html",
            {
                "model_types": get_submittable_model_types(),
                "model_categories": get_model_types_by_category(),
                "maintenance_mode": maintenance_mode,
                "maintenance_message": maintenance_message,
            },
        )

    if not model_key:
        raise Http404

    try:
        model_type = get_model_type(model_key)
    except KeyError as exc:
        raise Http404 from exc

    if request.method == "POST":
        form = model_type.get_form(request.POST, request.FILES)
        if maintenance_mode:
            form.add_error(None, maintenance_message)
        elif form.is_valid():
            try:
                model_type.validate(form.cleaned_data)
                input_payload = model_type.normalize_inputs(form.cleaned_data)
                runner_key = model_type.resolve_runner_key(form.cleaned_data)
                job = create_and_submit_job(
                    owner=request.user,
                    model_type=model_type,
                    name=form.cleaned_data.get("name", ""),
                    runner_key=runner_key,
                    sequences=input_payload.get("sequences", ""),
                    params=input_payload.get("params", {}),
                    model_key=model_type.key,
                    input_payload=input_payload,
                )
                return redirect("job_detail", job_id=job.id)
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = model_type.get_form()

    return render(
        request,
        model_type.template_name,
        {
            "form": form,
            "model_key": model_key,
            "page_title": f"New {model_type.name} Job",
            "maintenance_mode": maintenance_mode,
            "maintenance_message": maintenance_message,
            "disabled_runners": disabled_runners,
        },
    )


TERMINAL_STATUSES = {Job.Status.COMPLETED, Job.Status.FAILED, Job.Status.CANCELLED}


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    try:
        model_type = get_model_type(job.model_key)
    except KeyError:
        model_type = None

    output_context = (
        model_type.get_output_context(job)
        if model_type
        else _fallback_output_context(job)
    )

    log_context = {}
    if job.status in TERMINAL_STATUSES:
        log_context["stdout_log"] = read_log_tail(job, "stdout")
        log_context["stderr_log"] = read_log_tail(job, "stderr")

    return render(
        request, "jobs/detail.html", {"job": job, **output_context, **log_context}
    )


@login_required
def download_file(request, job_id, filename):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    outdir = (job.workdir / "output").resolve()
    file_path = (outdir / filename).resolve()

    if not file_path.is_relative_to(outdir):
        raise Http404
    if not file_path.exists() or not file_path.is_file():
        raise Http404

    return FileResponse(
        file_path.open("rb"),
        as_attachment=True,
        filename=file_path.name,
    )


@login_required
def download_log(request, job_id, log_type):
    if log_type not in ("stdout", "stderr"):
        raise Http404

    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)
    attempt = job.attempts.order_by("-attempt_number").first()
    if attempt is None:
        raise Http404

    raw_path = attempt.stdout_path if log_type == "stdout" else attempt.stderr_path
    if not raw_path:
        raise Http404

    log_path = Path(raw_path).resolve()
    workdir = job.workdir.resolve()
    if not log_path.is_relative_to(workdir):
        raise Http404
    if not log_path.exists() or not log_path.is_file():
        raise Http404

    return FileResponse(
        log_path.open("rb"),
        as_attachment=True,
        filename=log_path.name,
    )


@login_required
@require_POST
def job_cancel(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)
    if cancel_job(job, actor=request.user, source="user", reason="Cancelled by user"):
        messages.success(request, "Job cancelled.")
    else:
        messages.error(
            request,
            "Could not cancel the job because the local runtime did not stop cleanly.",
        )
    return redirect("job_detail", job_id=job.id)


@login_required
@require_POST
def job_delete(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)
    if hide_job(job, actor=request.user, source="user"):
        messages.success(request, "Job removed from your list.")
        return redirect("job_list")

    messages.error(
        request,
        "Could not remove the job because the active runtime did not stop cleanly.",
    )
    return redirect("job_detail", job_id=job.id)
