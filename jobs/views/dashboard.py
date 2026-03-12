from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from jobs.dashboard_stats import get_user_dashboard_stats


@login_required
def dashboard(request):
    stats = get_user_dashboard_stats(request.user)
    return render(request, "jobs/dashboard.html", {"stats": stats})
