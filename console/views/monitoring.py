from __future__ import annotations

from django.shortcuts import render

from console.decorators import console_required
from console.services.monitoring import (
    get_host_info,
    get_job_directory_stats,
    get_slurm_cluster_status,
)


@console_required
def monitoring(request):
    """System monitoring view with host and cluster status."""
    context = {
        "host_info": get_host_info(),
        "disk_stats": get_job_directory_stats(),
        "slurm_status": get_slurm_cluster_status(),
    }
    return render(request, "console/monitoring.html", context)

