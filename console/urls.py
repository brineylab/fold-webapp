from django.urls import path

from console import views

app_name = "console"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    
    # Jobs management
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<uuid:job_id>/cancel/", views.job_cancel, name="job_cancel"),
    path("jobs/bulk-action/", views.job_bulk_action, name="job_bulk_action"),
    
    # User management
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/quota/", views.user_update_quota, name="user_update_quota"),
    path("users/<int:user_id>/disable/", views.user_disable, name="user_disable"),
    path("users/<int:user_id>/enable/", views.user_enable, name="user_enable"),
    path("users/<int:user_id>/reset-password/", views.user_reset_password, name="user_reset_password"),
    path("users/<int:user_id>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    
    # Data cleanup
    path("cleanup/", views.cleanup_dashboard, name="cleanup_dashboard"),
    path("cleanup/run/", views.run_cleanup, name="run_cleanup"),
    path("cleanup/delete-orphan/", views.delete_orphan, name="delete_orphan"),
    path("cleanup/delete-all-orphans/", views.delete_all_orphans, name="delete_all_orphans"),
    
    # Monitoring
    path("monitoring/", views.monitoring, name="monitoring"),
    
    # Stats
    path("stats/", views.stats, name="stats"),
    path("stats/api/summary/", views.stats_api_summary, name="stats_api_summary"),
    
    # Audit log
    path("audit/", views.audit_log, name="audit_log"),
]

