from console.views.dashboard import dashboard
from console.views.jobs import job_list, job_detail, job_cancel, job_bulk_action
from console.views.monitoring import monitoring
from console.views.stats import stats, stats_api_summary
from console.views.audit import audit_log
from console.views.users import (
    user_list,
    user_detail,
    user_update_quota,
    user_disable,
    user_enable,
    user_reset_password,
    user_toggle_active,
    user_toggle_api_access,
    user_create_api_key,
    user_revoke_api_key,
    user_delete_api_key,
)
from console.views.cleanup import (
    cleanup_dashboard,
    run_cleanup,
    delete_orphan,
    delete_all_orphans,
)
from console.views.settings import (
    settings_page,
    toggle_maintenance,
    update_maintenance_message,
    toggle_runner,
    update_runner_reason,
)

__all__ = [
    "dashboard",
    "job_list",
    "job_detail",
    "job_cancel",
    "job_bulk_action",
    "monitoring",
    "stats",
    "stats_api_summary",
    "audit_log",
    "user_list",
    "user_detail",
    "user_update_quota",
    "user_disable",
    "user_enable",
    "user_reset_password",
    "user_toggle_active",
    "user_toggle_api_access",
    "user_create_api_key",
    "user_revoke_api_key",
    "user_delete_api_key",
    "cleanup_dashboard",
    "run_cleanup",
    "delete_orphan",
    "delete_all_orphans",
    "settings_page",
    "toggle_maintenance",
    "update_maintenance_message",
    "toggle_runner",
    "update_runner_reason",
]

