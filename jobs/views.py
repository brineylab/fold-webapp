from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import slurm
from jobs.forms import JobForm
from jobs.models import Job
from jobs.services import create_and_submit_job


def _job_queryset_for(user):
    return Job.objects.filter(owner=user, hidden_from_owner=False).select_related("owner")


@login_required
def job_list(request):
    jobs = _job_queryset_for(request.user).order_by("-created_at")[:100]
    return render(request, "jobs/list.html", {"jobs": jobs})


@login_required
def job_submit(request):
    if request.method == "POST":
        form = JobForm(request.POST)
        if form.is_valid():
            try:
                job = create_and_submit_job(
                    owner=request.user,
                    runner_key=form.cleaned_data["runner"],
                    sequences=form.cleaned_data["sequences"],
                    params={},
                )
                return redirect("job_detail", job_id=job.id)
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = JobForm()
    return render(request, "jobs/submit.html", {"form": form})


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


