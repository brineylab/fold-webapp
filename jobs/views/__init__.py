from jobs.views.account import (
    account_create_api_key,
    account_revoke_api_key,
    account_view,
)
from jobs.views.dashboard import dashboard
from jobs.views.jobs import (
    download_file,
    job_cancel,
    job_delete,
    job_detail,
    job_list,
    job_submit,
)

__all__ = [
    "account_create_api_key",
    "account_revoke_api_key",
    "account_view",
    "dashboard",
    "download_file",
    "job_cancel",
    "job_delete",
    "job_detail",
    "job_list",
    "job_submit",
]
