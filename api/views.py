from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from api.auth import api_auth_required
from jobs.models import Job
from jobs.services import create_and_submit_job
from model_types import get_model_type, get_submittable_model_types

import slurm


def _job_to_dict(job: Job) -> dict:
    """Serialize a Job to a JSON-compatible dict."""
    return {
        "id": str(job.id),
        "name": job.name,
        "model_key": job.model_key,
        "runner": job.runner,
        "status": job.status,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _output_files(job: Job) -> list[dict]:
    """List output files for a job."""
    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for p in sorted(outdir.rglob("*")):
            if p.is_file():
                rel = p.relative_to(outdir)
                files.append({"name": str(rel), "size": p.stat().st_size})
    return files


def _job_queryset_for(user):
    return Job.objects.filter(owner=user, hidden_from_owner=False).select_related(
        "owner"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/
# ---------------------------------------------------------------------------


@csrf_exempt
@api_auth_required
@require_GET
def model_list(request):
    """List available models and their accepted parameters."""
    models = []
    for mt in get_submittable_model_types():
        # Introspect form fields to describe parameters
        form = mt.get_form()
        params = {}
        for field_name, field in form.fields.items():
            if field_name == "name":
                continue  # name is a top-level job field, not a model param
            info = {
                "required": field.required,
                "help_text": str(field.help_text) if field.help_text else "",
            }
            if hasattr(field, "choices") and field.choices:
                info["choices"] = [
                    {"value": c[0], "label": c[1]} for c in field.choices
                ]
            if hasattr(field, "min_value") and field.min_value is not None:
                info["min_value"] = field.min_value
            if hasattr(field, "max_value") and field.max_value is not None:
                info["max_value"] = field.max_value
            if hasattr(field, "initial") and field.initial is not None:
                info["default"] = field.initial

            # Determine type hint
            from django import forms as djforms

            if isinstance(field, djforms.BooleanField):
                info["type"] = "boolean"
            elif isinstance(field, djforms.IntegerField):
                info["type"] = "integer"
            elif isinstance(field, djforms.FloatField):
                info["type"] = "number"
            elif isinstance(field, djforms.FileField):
                info["type"] = "file"
            elif isinstance(field, djforms.ChoiceField):
                info["type"] = "choice"
            else:
                info["type"] = "string"

            params[field_name] = info

        models.append({
            "key": mt.key,
            "name": mt.name,
            "category": mt.category,
            "help_text": mt.help_text,
            "parameters": params,
        })

    return JsonResponse({"models": models})


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/
# ---------------------------------------------------------------------------


@csrf_exempt
@api_auth_required
def job_create(request):
    """Submit a new job or list user's jobs."""
    if request.method == "GET":
        return _job_list(request)
    if request.method == "POST":
        return _job_submit(request)
    return JsonResponse({"error": "Method not allowed."}, status=405)


def _job_list(request):
    """List the user's recent jobs."""
    jobs = _job_queryset_for(request.user).order_by("-created_at")[:100]
    return JsonResponse({"jobs": [_job_to_dict(j) for j in jobs]})


def _job_submit(request):
    """Submit a new job via JSON or multipart."""
    content_type = request.content_type or ""

    if "multipart/form-data" in content_type:
        # Multipart: JSON payload in "data" field, files in file fields
        raw = request.POST.get("data", "{}")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON in 'data' field."}, status=400)
    elif "application/json" in content_type:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)
    else:
        return JsonResponse(
            {"error": "Content-Type must be application/json or multipart/form-data."},
            status=400,
        )

    model_key = data.get("model")
    if not model_key:
        return JsonResponse({"error": "Missing required field: model"}, status=400)

    try:
        model_type = get_model_type(model_key)
    except KeyError:
        return JsonResponse({"error": f"Unknown model: {model_key}"}, status=400)

    # Build cleaned_data dict from request data for the model type pipeline.
    # Merge JSON params with uploaded files so normalize_inputs sees them.
    cleaned_data = dict(data)
    cleaned_data.pop("model", None)

    # Inject uploaded files into cleaned_data (multipart requests)
    for file_key, uploaded_file in request.FILES.items():
        cleaned_data[file_key] = uploaded_file

    # Validate via form
    form = model_type.get_form(cleaned_data, request.FILES)
    if not form.is_valid():
        errors = {field: msgs for field, msgs in form.errors.items()}
        return JsonResponse({"error": "Validation failed.", "details": errors}, status=400)

    try:
        model_type.validate(form.cleaned_data)
        input_payload = model_type.normalize_inputs(form.cleaned_data)
        runner_key = model_type.resolve_runner_key(form.cleaned_data)
        job = create_and_submit_job(
            owner=request.user,
            model_type=model_type,
            name=form.cleaned_data.get("name", ""),
            runner_key=runner_key,
            sequences=input_payload.get("sequences", ""),
            params=input_payload.get("params", {}),
            model_key=model_type.key,
            input_payload=input_payload,
        )
        return JsonResponse({"job": _job_to_dict(job)}, status=201)
    except ValidationError as e:
        msg = e.message if hasattr(e, "message") else str(e)
        return JsonResponse({"error": msg}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<uuid>/
# POST /api/v1/jobs/<uuid>/cancel/
# DELETE /api/v1/jobs/<uuid>/
# ---------------------------------------------------------------------------


@csrf_exempt
@api_auth_required
def job_detail(request, job_id):
    """Job detail (GET) or soft-delete (DELETE)."""
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    if request.method == "GET":
        result = _job_to_dict(job)
        result["params"] = job.params
        result["output_files"] = _output_files(job)
        return JsonResponse({"job": result})

    if request.method == "DELETE":
        # Soft-delete: hide from owner
        if job.status == Job.Status.PENDING and job.slurm_job_id:
            slurm.cancel(job.slurm_job_id)
        job.hidden_from_owner = True
        job.save(update_fields=["hidden_from_owner"])
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed."}, status=405)


@csrf_exempt
@api_auth_required
@require_POST
def job_cancel(request, job_id):
    """Cancel a pending or running job."""
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    if job.status not in {Job.Status.PENDING, Job.Status.RUNNING}:
        return JsonResponse(
            {"error": f"Cannot cancel a job with status {job.status}."},
            status=400,
        )

    if job.slurm_job_id:
        slurm.cancel(job.slurm_job_id)

    job.status = Job.Status.FAILED
    job.error_message = "Cancelled by user via API"
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error_message", "completed_at"])

    return JsonResponse({"job": _job_to_dict(job)})


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<uuid>/download/<filename>
# ---------------------------------------------------------------------------


@csrf_exempt
@api_auth_required
@require_GET
def job_download(request, job_id, filename):
    """Download an output file from a job."""
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    outdir = (job.workdir / "output").resolve()
    file_path = (outdir / filename).resolve()

    # Prevent directory traversal
    if not file_path.is_relative_to(outdir):
        return JsonResponse({"error": "Invalid file path."}, status=400)
    if not file_path.exists() or not file_path.is_file():
        return JsonResponse({"error": "File not found."}, status=404)

    return FileResponse(
        file_path.open("rb"), as_attachment=True, filename=file_path.name
    )
