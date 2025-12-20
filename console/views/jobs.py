from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from console.decorators import console_required
from console.services.jobs import cancel_job, bulk_cancel_jobs, bulk_hide_jobs
from jobs.models import Job


@console_required
def job_list(request):
    """List all jobs across all users with search/filter capabilities."""
    jobs = Job.objects.select_related("owner").order_by("-created_at")
    
    # Search
    search = request.GET.get("search", "").strip()
    if search:
        jobs = jobs.filter(
            Q(id__icontains=search) |
            Q(name__icontains=search) |
            Q(owner__username__icontains=search) |
            Q(slurm_job_id__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get("status", "")
    if status and status in [s.value for s in Job.Status]:
        jobs = jobs.filter(status=status)
    
    # Filter by runner
    runner = request.GET.get("runner", "")
    if runner:
        jobs = jobs.filter(runner=runner)
    
    # Filter by hidden status
    hidden = request.GET.get("hidden", "")
    if hidden == "yes":
        jobs = jobs.filter(hidden_from_owner=True)
    elif hidden == "no":
        jobs = jobs.filter(hidden_from_owner=False)
    
    # Get unique runners for filter dropdown
    runners = Job.objects.values_list("runner", flat=True).distinct()
    
    # Pagination (simple limit for now)
    jobs = jobs[:200]
    
    context = {
        "jobs": jobs,
        "search": search,
        "status": status,
        "runner": runner,
        "hidden": hidden,
        "runners": runners,
        "statuses": Job.Status.choices,
    }
    return render(request, "console/jobs/list.html", context)


@console_required
def job_detail(request, job_id):
    """Detailed view of a single job for admin purposes."""
    job = get_object_or_404(Job.objects.select_related("owner"), id=job_id)
    
    # Get output files
    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for p in sorted(outdir.iterdir()):
            if p.is_file():
                files.append(p.name)
    
    # Get input files
    indir = job.workdir / "input"
    input_files = []
    if indir.exists() and indir.is_dir():
        for p in sorted(indir.iterdir()):
            if p.is_file():
                input_files.append(p.name)
    
    context = {
        "job": job,
        "files": files,
        "input_files": input_files,
    }
    return render(request, "console/jobs/detail.html", context)


@console_required
@require_POST
def job_cancel(request, job_id):
    """Cancel a single job."""
    job = get_object_or_404(Job, id=job_id)
    
    if cancel_job(job, request.user):
        messages.success(request, f"Job {job.id} cancelled successfully.")
    else:
        messages.warning(request, f"Job {job.id} could not be cancelled (not running or pending).")
    
    return redirect("console:job_detail", job_id=job_id)


@console_required
@require_POST
def job_bulk_action(request):
    """Handle bulk actions on multiple jobs."""
    action = request.POST.get("action", "")
    job_ids = request.POST.getlist("job_ids")
    
    if not job_ids:
        messages.warning(request, "No jobs selected.")
        return redirect("console:job_list")
    
    jobs = Job.objects.filter(id__in=job_ids)
    
    if action == "cancel":
        count = bulk_cancel_jobs(jobs, request.user)
        messages.success(request, f"Cancelled {count} job(s).")
    elif action == "hide":
        count = bulk_hide_jobs(jobs, request.user)
        messages.success(request, f"Hidden {count} job(s) from their owners.")
    else:
        messages.error(request, f"Unknown action: {action}")
    
    return redirect("console:job_list")

