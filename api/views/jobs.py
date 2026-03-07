from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from api.auth import api_auth_required
from api.views.shared import _job_queryset_for
from jobs.models import Job
from jobs.services import cancel_job, create_and_submit_job, hide_job, serialize_job
from model_types import get_model_type


@csrf_exempt
@api_auth_required
def job_create(request):
    if request.method == "GET":
        return _job_list(request)
    if request.method == "POST":
        return _job_submit(request)
    return JsonResponse({"error": "Method not allowed."}, status=405)


def _job_list(request):
    jobs = _job_queryset_for(request.user).order_by("-created_at")[:100]
    return JsonResponse({"jobs": [serialize_job(job) for job in jobs]})


def _job_submit(request):
    content_type = request.content_type or ""

    if "multipart/form-data" in content_type:
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

    cleaned_data = dict(data)
    cleaned_data.pop("model", None)
    for file_key, uploaded_file in request.FILES.items():
        cleaned_data[file_key] = uploaded_file

    form = model_type.get_form(cleaned_data, request.FILES)
    if not form.is_valid():
        errors = {field: messages for field, messages in form.errors.items()}
        return JsonResponse(
            {"error": "Validation failed.", "details": errors},
            status=400,
        )

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
        return JsonResponse({"job": serialize_job(job)}, status=201)
    except ValidationError as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        return JsonResponse({"error": message}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@api_auth_required
def job_detail(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    if request.method == "GET":
        result = serialize_job(
            job,
            include_params=True,
            include_output_files=True,
            include_attempts=True,
        )
        return JsonResponse({"job": result})

    if request.method == "DELETE":
        if not hide_job(job, actor=request.user, source="api"):
            return JsonResponse(
                {
                    "error": (
                        "Could not delete the job because the active runtime did "
                        "not stop cleanly."
                    )
                },
                status=409,
            )
        return JsonResponse({"status": "deleted"})

    return JsonResponse({"error": "Method not allowed."}, status=405)


@csrf_exempt
@api_auth_required
@require_POST
def job_cancel(request, job_id):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    if job.status not in {Job.Status.PENDING, Job.Status.RUNNING}:
        return JsonResponse(
            {"error": f"Cannot cancel a job with status {job.status}."},
            status=400,
        )

    if not cancel_job(
        job,
        actor=request.user,
        source="api",
        reason="Cancelled by user via API",
    ):
        return JsonResponse(
            {
                "error": (
                    "Could not cancel the job because the local runtime did not "
                    "stop cleanly."
                )
            },
            status=409,
        )
    return JsonResponse({"job": serialize_job(job)})


@csrf_exempt
@api_auth_required
@require_GET
def job_download(request, job_id, filename):
    job = get_object_or_404(_job_queryset_for(request.user), id=job_id)

    outdir = (job.workdir / "output").resolve()
    file_path = (outdir / filename).resolve()

    if not file_path.is_relative_to(outdir):
        return JsonResponse({"error": "Invalid file path."}, status=400)
    if not file_path.exists() or not file_path.is_file():
        return JsonResponse({"error": "File not found."}, status=404)

    return FileResponse(
        file_path.open("rb"),
        as_attachment=True,
        filename=file_path.name,
    )
