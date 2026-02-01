from django.urls import path

from api import views

app_name = "api"

urlpatterns = [
    path("v1/models/", views.model_list, name="model_list"),
    path("v1/jobs/", views.job_create, name="job_create"),
    path("v1/jobs/<uuid:job_id>/", views.job_detail, name="job_detail"),
    path("v1/jobs/<uuid:job_id>/cancel/", views.job_cancel, name="job_cancel"),
    path(
        "v1/jobs/<uuid:job_id>/download/<path:filename>",
        views.job_download,
        name="job_download",
    ),
]
