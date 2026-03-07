from __future__ import annotations

from collections.abc import Mapping

from console.models import ActionLog


def log_action(
    *,
    scope: str,
    action: str,
    message: str,
    actor=None,
    source: str = "",
    job=None,
    target_user=None,
    target_label: str = "",
    runner_key: str = "",
    metadata: Mapping | None = None,
):
    """Persist a focused domain action for operational review."""
    actor_obj = actor if getattr(actor, "is_authenticated", False) else None

    resolved_target_label = (target_label or "").strip()
    if not resolved_target_label:
        if target_user is not None:
            resolved_target_label = target_user.username
        elif runner_key:
            resolved_target_label = runner_key
        elif job is not None:
            resolved_target_label = str(job.id)

    return ActionLog.objects.create(
        scope=scope,
        action=action,
        source=(source or "").strip(),
        actor=actor_obj,
        job=job,
        target_user=target_user,
        target_label=resolved_target_label,
        runner_key=(runner_key or "").strip(),
        message=message,
        metadata=dict(metadata or {}),
    )
