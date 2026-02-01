from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import slurm
from console.models import SiteSettings
from jobs.forms import get_disabled_runners
from jobs.models import Job
from jobs.services import create_and_submit_job
from model_types import get_model_type, get_submittable_model_types


def _job_queryset_for(user):
    return Job.objects.filter(owner=user, hidden_from_owner=False).select_related(
        "owner"
    )


@login_required
def job_list(request):
    jobs = _job_queryset_for(request.user).order_by("-created_at")[:100]
    return render(request, "jobs/list.html", {"jobs": jobs})


@login_required
def job_submit(request):
    # Check maintenance mode
    site_settings = SiteSettings.get_settings()
    maintenance_mode = site_settings.maintenance_mode
    maintenance_message = site_settings.maintenance_message

    # Get list of disabled runners
    disabled_runners = get_disabled_runners()

    model_key = request.GET.get("model") or request.POST.get("model")

    # No model selected -- show the model selection landing page
    if not model_key and request.method == "GET":
        return render(request, "jobs/select_model.html", {
            "model_types": get_submittable_model_types(),
            "maintenance_mode": maintenance_mode,
            "maintenance_message": maintenance_message,
        })

    # Resolve the selected model type
    if not model_key:
        raise Http404
    try:
        model_type = get_model_type(model_key)
    except KeyError as exc:
        raise Http404 from exc

    if request.method == "POST":
        # Block submission if in maintenance mode
        if maintenance_mode:
            form = model_type.get_form(request.POST, request.FILES)
            form.add_error(None, maintenance_message)
        else:
            form = model_type.get_form(request.POST, request.FILES)
            if form.is_valid():
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
                except Exception as e:
                    form.add_error(None, str(e))
    else:
        form = model_type.get_form()

    page_title = f"New {model_type.name} Job"
    return render(request, model_type.template_name, {
        "form": form,
        "model_key": model_key,
        "page_title": page_title,
        "maintenance_mode": maintenance_mode,
        "maintenance_message": maintenance_message,
        "disabled_runners": disabled_runners,
    })


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for p in sorted(outdir.iterdir()):
            if p.is_file():
                files.append(p.name)

    return render(request, "jobs/detail.html", {"job": job, "files": files})


@login_required
def download_file(request, job_id, filename):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    safe_name = Path(filename).name  # prevent directory traversal
    file_path = job.workdir / "output" / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise Http404

    return FileResponse(open(file_path, "rb"), as_attachment=True, filename=safe_name)


@login_required
@require_POST
def job_cancel(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    if job.status in {Job.Status.PENDING, Job.Status.RUNNING} and job.slurm_job_id:
        slurm.cancel(job.slurm_job_id)
        job.status = Job.Status.FAILED
        job.error_message = "Cancelled by user"
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])

    return redirect("job_detail", job_id=job.id)


@login_required
@require_POST
def job_delete(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    # For pending jobs, cancel the SLURM job first
    if job.status == Job.Status.PENDING and job.slurm_job_id:
        slurm.cancel(job.slurm_job_id)

    # Soft delete: hide from owner but keep for admins
    job.hidden_from_owner = True
    job.save(update_fields=["hidden_from_owner"])

    return redirect("job_list")
