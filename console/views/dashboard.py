from __future__ import annotations

from django.shortcuts import render

from console.decorators import console_required
from console.services.monitoring import get_dashboard_stats


@console_required
def dashboard(request):
    """Main dashboard view with high-level counters and alerts."""
    stats = get_dashboard_stats()
    return render(request, "console/dashboard.html", {"stats": stats})

