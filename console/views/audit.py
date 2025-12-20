from __future__ import annotations

from django.shortcuts import render

from console.decorators import console_required


@console_required
def audit_log(request):
    """
    Audit log view showing history of job changes.
    
    Uses django-simple-history to display historical records.
    """
    # Import here to avoid issues if simple_history isn't installed yet
    try:
        from jobs.models import Job
        
        # Check if history is available
        if hasattr(Job, "history"):
            history_qs = Job.history.select_related("history_user").order_by("-history_date")
            
            # Filter by user
            user_filter = request.GET.get("user", "").strip()
            if user_filter:
                history_qs = history_qs.filter(history_user__username__icontains=user_filter)
            
            # Filter by action type
            action_filter = request.GET.get("action", "")
            if action_filter:
                history_qs = history_qs.filter(history_type=action_filter)
            
            # Filter by job ID
            job_filter = request.GET.get("job", "").strip()
            if job_filter:
                history_qs = history_qs.filter(id__icontains=job_filter)
            
            # Limit results
            history_records = list(history_qs[:200])
            
            context = {
                "history_records": history_records,
                "user_filter": user_filter,
                "action_filter": action_filter,
                "job_filter": job_filter,
                "history_available": True,
            }
        else:
            context = {
                "history_records": [],
                "history_available": False,
                "message": "History tracking not configured. Add HistoricalRecords to Job model.",
            }
    except Exception as e:
        context = {
            "history_records": [],
            "history_available": False,
            "message": f"Error loading history: {e}",
        }
    
    return render(request, "console/audit.html", context)

