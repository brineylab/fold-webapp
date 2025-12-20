from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import django
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from jobs.models import Job


def get_dashboard_stats() -> dict[str, Any]:
    """
    Get high-level statistics for the dashboard.
    
    Returns:
        Dictionary containing job counters, queue depth, recent failures, and disk usage.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    
    # Job status counters
    all_jobs = Job.objects.all()
    jobs_24h = all_jobs.filter(created_at__gte=last_24h)
    
    status_counts_all = dict(all_jobs.values("status").annotate(count=Count("id")).values_list("status", "count"))
    status_counts_24h = dict(jobs_24h.values("status").annotate(count=Count("id")).values_list("status", "count"))
    
    # Queue depth (pending jobs)
    queue_depth = all_jobs.filter(status=Job.Status.PENDING).count()
    
    # Recent failures
    recent_failures = list(
        all_jobs.filter(status=Job.Status.FAILED)
        .order_by("-completed_at")[:5]
        .values("id", "name", "owner__username", "error_message", "completed_at")
    )
    
    # Disk usage
    disk_usage = get_job_directory_stats()
    
    return {
        "status_counts_all": {
            "pending": status_counts_all.get(Job.Status.PENDING, 0),
            "running": status_counts_all.get(Job.Status.RUNNING, 0),
            "completed": status_counts_all.get(Job.Status.COMPLETED, 0),
            "failed": status_counts_all.get(Job.Status.FAILED, 0),
        },
        "status_counts_24h": {
            "pending": status_counts_24h.get(Job.Status.PENDING, 0),
            "running": status_counts_24h.get(Job.Status.RUNNING, 0),
            "completed": status_counts_24h.get(Job.Status.COMPLETED, 0),
            "failed": status_counts_24h.get(Job.Status.FAILED, 0),
        },
        "queue_depth": queue_depth,
        "recent_failures": recent_failures,
        "disk_usage": disk_usage,
        "total_jobs": all_jobs.count(),
        "jobs_24h": jobs_24h.count(),
    }


def get_host_info() -> dict[str, Any]:
    """
    Get information about the host system.
    
    Returns:
        Dictionary containing hostname, Python version, Django version, etc.
    """
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "django_version": django.__version__,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }


def get_job_directory_stats() -> dict[str, Any]:
    """
    Get statistics about the job data directory.
    
    Returns:
        Dictionary containing disk usage information for JOB_BASE_DIR.
    """
    job_base_dir = getattr(settings, "JOB_BASE_DIR", None)
    
    if job_base_dir is None:
        return {
            "configured": False,
            "error": "JOB_BASE_DIR not configured",
        }
    
    job_base_dir = Path(job_base_dir)
    
    if not job_base_dir.exists():
        return {
            "configured": True,
            "path": str(job_base_dir),
            "exists": False,
        }
    
    try:
        usage = shutil.disk_usage(job_base_dir)
        
        # Count job directories
        job_count = sum(1 for p in job_base_dir.iterdir() if p.is_dir())
        
        return {
            "configured": True,
            "path": str(job_base_dir),
            "exists": True,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(usage.used / usage.total * 100, 1),
            "job_directories": job_count,
        }
    except Exception as e:
        return {
            "configured": True,
            "path": str(job_base_dir),
            "exists": True,
            "error": str(e),
        }


def get_slurm_cluster_status() -> dict[str, Any]:
    """
    Get SLURM cluster status.
    
    This is a stub that can be expanded to query actual SLURM status.
    
    Returns:
        Dictionary containing cluster connectivity and status information.
    """
    fake_slurm = getattr(settings, "FAKE_SLURM", False)
    
    if fake_slurm:
        return {
            "mode": "fake",
            "connected": True,
            "message": "Running in FAKE_SLURM mode (no real cluster)",
        }
    
    # TODO: Implement real SLURM status checks
    # This could use sinfo, squeue, etc. to get cluster status
    return {
        "mode": "real",
        "connected": None,  # Unknown until we implement actual checks
        "message": "SLURM status check not yet implemented",
        # Future fields:
        # "nodes_total": ...,
        # "nodes_available": ...,
        # "nodes_down": ...,
        # "jobs_queued": ...,
        # "jobs_running": ...,
    }

