from django.urls import path

from jobs import views


urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("jobs/new/", views.job_submit, name="job_submit"),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<uuid:job_id>/download/<path:filename>", views.download_file, name="download_file"),
    path("jobs/<uuid:job_id>/cancel/", views.job_cancel, name="job_cancel"),
    path("jobs/<uuid:job_id>/delete/", views.job_delete, name="job_delete"),
    path("account/", views.account_view, name="account"),
    path("account/api-keys/create/", views.account_create_api_key, name="account_create_api_key"),
    path("account/api-keys/<int:key_id>/revoke/", views.account_revoke_api_key, name="account_revoke_api_key"),
]


