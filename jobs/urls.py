from django.urls import path

from jobs import views


urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("jobs/new/", views.job_submit, name="job_submit"),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<uuid:job_id>/download/<path:filename>", views.download_file, name="download_file"),
    path("jobs/<uuid:job_id>/cancel/", views.job_cancel, name="job_cancel"),
]


