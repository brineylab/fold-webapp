from __future__ import annotations

import json

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from console.decorators import console_required
from console.models import RunnerConfig, SiteSettings
from runners import all_runners


@console_required
def settings_page(request):
    """Main settings page showing maintenance mode and runner configuration."""
    site_settings = SiteSettings.get_settings()
    
    # Ensure RunnerConfig exists for all registered runners
    registered_runners = all_runners()
    runner_configs = []
    for runner in registered_runners:
        config = RunnerConfig.get_config(runner.key)
        runner_configs.append({
            "config": config,
            "name": runner.name,
            "key": runner.key,
            "extra_env_json": json.dumps(config.extra_env, indent=2) if config.extra_env else "",
            "extra_mounts_json": json.dumps(config.extra_mounts, indent=2) if config.extra_mounts else "",
        })
    
    return render(request, "console/settings.html", {
        "site_settings": site_settings,
        "runner_configs": runner_configs,
    })


@console_required
@require_POST
def toggle_maintenance(request):
    """Toggle maintenance mode on/off."""
    site_settings = SiteSettings.get_settings()
    
    # Toggle the mode
    new_state = not site_settings.maintenance_mode
    site_settings.maintenance_mode = new_state
    site_settings.updated_by = request.user
    
    # Update message if provided
    message = request.POST.get("maintenance_message", "").strip()
    if message:
        site_settings.maintenance_message = message
    
    site_settings.save()
    
    if new_state:
        messages.warning(request, "Maintenance mode is now ENABLED. New job submissions are blocked.")
    else:
        messages.success(request, "Maintenance mode is now DISABLED. Job submissions are allowed.")
    
    return redirect("console:settings")


@console_required
@require_POST
def update_maintenance_message(request):
    """Update the maintenance message without toggling mode."""
    site_settings = SiteSettings.get_settings()
    
    message = request.POST.get("maintenance_message", "").strip()
    if message:
        site_settings.maintenance_message = message
        site_settings.updated_by = request.user
        site_settings.save()
        messages.success(request, "Maintenance message updated.")
    else:
        messages.error(request, "Maintenance message cannot be empty.")
    
    return redirect("console:settings")


@console_required
@require_POST
def toggle_runner(request, runner_key: str):
    """Toggle a specific runner on/off."""
    config = get_object_or_404(RunnerConfig, runner_key=runner_key)
    
    # Toggle enabled state
    new_state = not config.enabled
    config.enabled = new_state
    config.updated_by = request.user
    
    # If disabling, capture the reason
    if not new_state:
        reason = request.POST.get("disabled_reason", "").strip()
        config.disabled_reason = reason
    else:
        config.disabled_reason = ""
    
    config.save()
    
    # Get runner name for the message
    runner_name = runner_key
    for runner in all_runners():
        if runner.key == runner_key:
            runner_name = runner.name
            break
    
    if new_state:
        messages.success(request, f"{runner_name} is now ENABLED.")
    else:
        messages.warning(request, f"{runner_name} is now DISABLED.")
    
    return redirect("console:settings")


@console_required
@require_POST
def update_runner_reason(request, runner_key: str):
    """Update the disabled reason for a runner."""
    config = get_object_or_404(RunnerConfig, runner_key=runner_key)

    reason = request.POST.get("disabled_reason", "").strip()
    config.disabled_reason = reason
    config.updated_by = request.user
    config.save()

    messages.success(request, f"Updated reason for {runner_key}.")

    return redirect("console:settings")


@console_required
@require_POST
def update_runner_config(request, runner_key: str):
    """Update SLURM resource and container settings for a runner."""
    config = get_object_or_404(RunnerConfig, runner_key=runner_key)

    # Get runner name for messages
    runner_name = runner_key
    for runner in all_runners():
        if runner.key == runner_key:
            runner_name = runner.name
            break

    # SLURM resource fields
    config.partition = request.POST.get("partition", "").strip()
    config.time_limit = request.POST.get("time_limit", "").strip()

    # Numeric fields
    errors = []
    for field, label in [("gpus", "GPUs"), ("cpus", "CPUs"), ("mem_gb", "Memory (GB)")]:
        raw = request.POST.get(field, "").strip()
        if raw == "":
            setattr(config, field, 0 if field == "gpus" else 1 if field == "cpus" else 8)
        else:
            try:
                val = int(raw)
                if val < 0:
                    raise ValueError
                setattr(config, field, val)
            except (ValueError, TypeError):
                errors.append(f"{label} must be a non-negative integer.")

    # Container fields
    config.image_uri = request.POST.get("image_uri", "").strip()

    # JSON fields
    extra_env_raw = request.POST.get("extra_env", "").strip()
    if extra_env_raw:
        try:
            parsed = json.loads(extra_env_raw)
            if not isinstance(parsed, dict):
                errors.append("Extra env must be a JSON object (e.g. {}).")
            else:
                config.extra_env = parsed
        except json.JSONDecodeError:
            errors.append("Extra env contains invalid JSON.")
    else:
        config.extra_env = {}

    extra_mounts_raw = request.POST.get("extra_mounts", "").strip()
    if extra_mounts_raw:
        try:
            parsed = json.loads(extra_mounts_raw)
            if not isinstance(parsed, list):
                errors.append("Extra mounts must be a JSON array (e.g. []).")
            else:
                config.extra_mounts = parsed
        except json.JSONDecodeError:
            errors.append("Extra mounts contains invalid JSON.")
    else:
        config.extra_mounts = []

    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect("console:settings")

    config.updated_by = request.user
    config.save()

    messages.success(request, f"Configuration updated for {runner_name}.")
    return redirect("console:settings")

