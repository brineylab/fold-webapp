from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from console.decorators import console_required, superops_required
from console.services.cleanup import (
    cleanup_jobs,
    get_cleanup_summary,
    get_jobs_for_cleanup,
    detect_orphan_workdirs,
    detect_orphan_jobs,
    delete_orphan_workdir,
)


@console_required
def cleanup_dashboard(request):
    """Dashboard showing cleanup status and options."""
    summary = get_cleanup_summary()
    
    # Get detailed lists for display
    jobs_for_cleanup = get_jobs_for_cleanup()[:50]  # Limit for display
    orphan_workdirs = detect_orphan_workdirs()[:50]
    orphan_jobs = list(detect_orphan_jobs()[:50])
    
    context = {
        "summary": summary,
        "jobs_for_cleanup": jobs_for_cleanup,
        "orphan_workdirs": orphan_workdirs,
        "orphan_jobs": orphan_jobs,
    }
    return render(request, "console/cleanup.html", context)


@superops_required
@require_POST
def run_cleanup(request):
    """Execute the cleanup operation."""
    dry_run = request.POST.get("dry_run", "1") == "1"
    override_days = request.POST.get("override_days", "").strip()
    
    kwargs = {"dry_run": dry_run}
    if override_days:
        try:
            kwargs["override_days"] = int(override_days)
        except ValueError:
            messages.error(request, "Invalid override days value")
            return redirect("console:cleanup_dashboard")
    
    result = cleanup_jobs(**kwargs)
    
    if dry_run:
        messages.info(
            request,
            f"Dry run complete: {result['cleaned']} job(s) would be cleaned, "
            f"{result['bytes_freed_mb']} MB would be freed"
        )
    else:
        messages.success(
            request,
            f"Cleanup complete: {result['cleaned']} job(s) cleaned, "
            f"{result['bytes_freed_mb']} MB freed"
        )
    
    return redirect("console:cleanup_dashboard")


@superops_required
@require_POST
def delete_orphan(request):
    """Delete a specific orphan workdir."""
    path = request.POST.get("path", "")
    
    if not path:
        messages.error(request, "No path specified")
        return redirect("console:cleanup_dashboard")
    
    if delete_orphan_workdir(path):
        messages.success(request, f"Deleted orphan workdir: {path}")
    else:
        messages.error(request, f"Failed to delete orphan workdir: {path}")
    
    return redirect("console:cleanup_dashboard")


@superops_required
@require_POST
def delete_all_orphans(request):
    """Delete all orphan workdirs."""
    orphans = detect_orphan_workdirs()
    
    deleted = 0
    failed = 0
    
    for orphan in orphans:
        if delete_orphan_workdir(orphan["path"]):
            deleted += 1
        else:
            failed += 1
    
    if failed > 0:
        messages.warning(
            request,
            f"Deleted {deleted} orphan workdir(s), {failed} failed"
        )
    else:
        messages.success(request, f"Deleted {deleted} orphan workdir(s)")
    
    return redirect("console:cleanup_dashboard")

