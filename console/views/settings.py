from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from console.decorators import console_required
from console.models import RunnerConfig, SiteSettings
from console.services.audit import log_action
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
    previous_state = site_settings.maintenance_mode
    previous_message = site_settings.maintenance_message
    
    # Toggle the mode
    new_state = not site_settings.maintenance_mode
    site_settings.maintenance_mode = new_state
    site_settings.updated_by = request.user
    
    # Update message if provided
    message = request.POST.get("maintenance_message", "").strip()
    if message:
        site_settings.maintenance_message = message
    
    site_settings.save()
    log_action(
        scope="settings",
        action="maintenance_enabled" if new_state else "maintenance_disabled",
        actor=request.user,
        source="console",
        target_label="site",
        message=(
            f"Maintenance mode {'enabled' if new_state else 'disabled'}."
        ),
        metadata={
            "previous_state": previous_state,
            "current_state": new_state,
            "previous_message": previous_message,
            "current_message": site_settings.maintenance_message,
        },
    )
    
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
    previous_message = site_settings.maintenance_message
    
    message = request.POST.get("maintenance_message", "").strip()
    if message:
        site_settings.maintenance_message = message
        site_settings.updated_by = request.user
        site_settings.save()
        log_action(
            scope="settings",
            action="maintenance_message_updated",
            actor=request.user,
            source="console",
            target_label="site",
            message="Updated the maintenance message.",
            metadata={
                "previous_message": previous_message,
                "current_message": site_settings.maintenance_message,
            },
        )
        messages.success(request, "Maintenance message updated.")
    else:
        messages.error(request, "Maintenance message cannot be empty.")
    
    return redirect("console:settings")


@console_required
@require_POST
def toggle_runner(request, runner_key: str):
    """Toggle a specific runner on/off."""
    config = get_object_or_404(RunnerConfig, runner_key=runner_key)
    previous_state = config.enabled
    previous_reason = config.disabled_reason
    
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
    log_action(
        scope="settings",
        action="runner_enabled" if new_state else "runner_disabled",
        actor=request.user,
        source="console",
        runner_key=runner_key,
        message=f"{runner_key} {'enabled' if new_state else 'disabled'}.",
        metadata={
            "previous_state": previous_state,
            "current_state": new_state,
            "previous_reason": previous_reason,
            "current_reason": config.disabled_reason,
        },
    )
    
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
    previous_reason = config.disabled_reason

    reason = request.POST.get("disabled_reason", "").strip()
    config.disabled_reason = reason
    config.updated_by = request.user
    config.save()
    log_action(
        scope="settings",
        action="runner_reason_updated",
        actor=request.user,
        source="console",
        runner_key=runner_key,
        message=f"Updated disabled reason for {runner_key}.",
        metadata={"previous_reason": previous_reason, "current_reason": reason},
    )

    messages.success(request, f"Updated reason for {runner_key}.")

    return redirect("console:settings")


@console_required
@require_POST
def update_runner_config(request, runner_key: str):
    """Update the minimal runtime configuration for a runner."""
    config = get_object_or_404(RunnerConfig, runner_key=runner_key)
    previous_image_uri = config.image_uri

    # Get runner name for messages
    runner_name = runner_key
    for runner in all_runners():
        if runner.key == runner_key:
            runner_name = runner.name
            break

    config.image_uri = request.POST.get("image_uri", "").strip()

    config.updated_by = request.user
    config.save()
    log_action(
        scope="settings",
        action="runner_config_updated",
        actor=request.user,
        source="console",
        runner_key=runner_key,
        message=f"Updated runtime configuration for {runner_name}.",
        metadata={
            "previous_image_uri": previous_image_uri,
            "current_image_uri": config.image_uri,
        },
    )

    messages.success(request, f"Configuration updated for {runner_name}.")
    return redirect("console:settings")
