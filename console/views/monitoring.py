from __future__ import annotations

from django.shortcuts import render

from console.decorators import console_required
from console.services.monitoring import (
    get_execution_backend_status,
    get_host_info,
    get_job_directory_stats,
)


@console_required
def monitoring(request):
    """System monitoring view with host and cluster status."""
    context = {
        "host_info": get_host_info(),
        "disk_stats": get_job_directory_stats(),
        "backend_status": get_execution_backend_status(),
    }
    return render(request, "console/monitoring.html", context)
