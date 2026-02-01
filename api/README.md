# REST API

Programmatic access to BioPortal for submitting and managing structure prediction jobs. The API uses Bearer token authentication and returns JSON responses. No additional dependencies are required beyond Django itself.

## Authentication

Every request must include an API key in the `Authorization` header:

```
Authorization: Bearer <your-api-key>
```

API access is opt-in. An administrator must enable API access for each user via the Ops Console, and the user (or admin) must then create an API key. Keys are 64-character hex tokens shown only once at creation time.

### Obtaining a Key

**Via the web UI (self-service):**

1. An admin enables API access for your account in the Ops Console (Users > your profile > Enable API).
2. Log in to BioPortal, open the user menu, and click **Account**.
3. Click **Create Key**, optionally provide a label, and copy the key immediately.

**Via the Ops Console (admin):**

Navigate to Users > select user > API Access card > **Create Key**.

**Via the command line:**

```bash
python manage.py create_api_key <username> --label "my script"
```

### Error Responses

| Status | Meaning |
|--------|---------|
| 401 | Missing, empty, invalid, or revoked API key |
| 403 | User account inactive, or API access not enabled for the user |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/models/` | List available models and their parameters |
| `POST` | `/api/v1/jobs/` | Submit a new job |
| `GET` | `/api/v1/jobs/` | List your jobs (most recent 100) |
| `GET` | `/api/v1/jobs/<uuid>/` | Get job details and output file list |
| `POST` | `/api/v1/jobs/<uuid>/cancel/` | Cancel a pending or running job |
| `DELETE` | `/api/v1/jobs/<uuid>/` | Soft-delete a job |
| `GET` | `/api/v1/jobs/<uuid>/download/<filename>` | Download an output file |

---

### List Models

```
GET /api/v1/models/
```

Returns all registered model types with their accepted parameters, types, defaults, and constraints. Use this to discover which models are available and what fields each one expects.

**Response:**

```json
{
  "models": [
    {
      "key": "boltz2",
      "name": "Boltz-2",
      "category": "Structure Prediction",
      "help_text": "Predict biomolecular structure and binding affinity with Boltz-2...",
      "parameters": {
        "sequences": {
          "type": "string",
          "required": false,
          "help_text": "Paste one or more FASTA-formatted sequences..."
        },
        "input_file": {
          "type": "file",
          "required": false,
          "help_text": "Upload a Boltz-2 YAML input file..."
        },
        "output_format": {
          "type": "choice",
          "required": false,
          "default": "mmcif",
          "choices": [
            {"value": "mmcif", "label": "mmCIF"},
            {"value": "pdb", "label": "PDB"}
          ]
        }
      }
    }
  ]
}
```

---

### Submit a Job

```
POST /api/v1/jobs/
```

Accepts `application/json` for text-only submissions or `multipart/form-data` when files need to be uploaded.

**JSON body fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `model` | yes | Model key (e.g. `boltz2`, `chai1`, `protein_mpnn`, `ligand_mpnn`) |
| `name` | no | Human-readable job name |
| *model params* | varies | Any parameters listed by `GET /api/v1/models/` for the chosen model |

All standard quota checks, maintenance mode checks, and runner validation apply identically to API submissions and web submissions.

**Response (201):**

```json
{
  "job": {
    "id": "a1b2c3d4-...",
    "name": "my prediction",
    "model_key": "boltz2",
    "runner": "boltz-2",
    "status": "PENDING",
    "error_message": "",
    "created_at": "2025-06-15T10:30:00+00:00",
    "submitted_at": "2025-06-15T10:30:01+00:00",
    "completed_at": null
  }
}
```

**Error response (400):**

```json
{
  "error": "Validation failed.",
  "details": {
    "sequences": ["This field is required."]
  }
}
```

---

### List Jobs

```
GET /api/v1/jobs/
```

Returns the most recent 100 jobs for the authenticated user (excludes soft-deleted jobs).

**Response:**

```json
{
  "jobs": [
    {
      "id": "a1b2c3d4-...",
      "name": "my prediction",
      "model_key": "boltz2",
      "runner": "boltz-2",
      "status": "COMPLETED",
      "error_message": "",
      "created_at": "2025-06-15T10:30:00+00:00",
      "submitted_at": "2025-06-15T10:30:01+00:00",
      "completed_at": "2025-06-15T10:45:00+00:00"
    }
  ]
}
```

---

### Get Job Detail

```
GET /api/v1/jobs/<uuid>/
```

Returns full job details including parameters and a list of output files (available once the job completes).

**Response:**

```json
{
  "job": {
    "id": "a1b2c3d4-...",
    "name": "my prediction",
    "model_key": "boltz2",
    "runner": "boltz-2",
    "status": "COMPLETED",
    "error_message": "",
    "created_at": "2025-06-15T10:30:00+00:00",
    "submitted_at": "2025-06-15T10:30:01+00:00",
    "completed_at": "2025-06-15T10:45:00+00:00",
    "params": {"output_format": "mmcif"},
    "output_files": [
      {"name": "prediction.cif", "size": 128000},
      {"name": "scores.json", "size": 450}
    ]
  }
}
```

---

### Cancel a Job

```
POST /api/v1/jobs/<uuid>/cancel/
```

Cancels a job that is `PENDING` or `RUNNING`. Returns 400 if the job has already completed or failed.

**Response:**

```json
{
  "job": {
    "id": "a1b2c3d4-...",
    "status": "FAILED",
    "error_message": "Cancelled by user via API"
  }
}
```

---

### Delete a Job

```
DELETE /api/v1/jobs/<uuid>/
```

Soft-deletes a job (hides it from your job list). Pending jobs are cancelled first. The job data is retained for admin visibility.

**Response:**

```json
{"status": "deleted"}
```

---

### Download an Output File

```
GET /api/v1/jobs/<uuid>/download/<filename>
```

Downloads a single output file. Use the `output_files` list from the job detail endpoint to discover available filenames. Returns the raw file as an attachment.

---

## Step-by-Step Usage Examples

The examples below use `curl`. Replace `$KEY` with your API key and `$BASE` with your server URL (e.g. `http://localhost:8000`).

```bash
export KEY="your-api-key-here"
export BASE="http://localhost:8000"
```

### 1. Discover available models

```bash
curl -s -H "Authorization: Bearer $KEY" $BASE/api/v1/models/ | python -m json.tool
```

### 2. Submit a Boltz-2 job with FASTA sequences

```bash
curl -s -X POST $BASE/api/v1/jobs/ \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "boltz2",
    "name": "my complex",
    "sequences": ">chain_A\nMKTAYIAKQRQISFVKSHFSRQLE\n>chain_B\nMAGFLKVVQLL",
    "output_format": "pdb"
  }' | python -m json.tool
```

Save the returned `id` for subsequent requests:

```bash
JOB_ID="a1b2c3d4-..."   # from the response
```

### 3. Submit a ProteinMPNN job with a PDB file upload

File uploads require `multipart/form-data`. The JSON parameters go in a field named `data`, and files go in their own fields:

```bash
curl -s -X POST $BASE/api/v1/jobs/ \
  -H "Authorization: Bearer $KEY" \
  -F "data={\"model\": \"protein_mpnn\", \"name\": \"design run\", \"num_sequences\": 16, \"temperature\": 0.2}" \
  -F "pdb_file=@structure.pdb" | python -m json.tool
```

### 4. Poll for job completion

```bash
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $KEY" \
    $BASE/api/v1/jobs/$JOB_ID/ | python -c "import sys,json; print(json.load(sys.stdin)['job']['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] && break
  sleep 30
done
```

### 5. List output files

```bash
curl -s -H "Authorization: Bearer $KEY" \
  $BASE/api/v1/jobs/$JOB_ID/ | python -m json.tool
```

Check the `output_files` array in the response.

### 6. Download a result file

```bash
curl -s -H "Authorization: Bearer $KEY" \
  -o prediction.cif \
  $BASE/api/v1/jobs/$JOB_ID/download/prediction.cif
```

### 7. List all your jobs

```bash
curl -s -H "Authorization: Bearer $KEY" $BASE/api/v1/jobs/ | python -m json.tool
```

### 8. Cancel a running job

```bash
curl -s -X POST -H "Authorization: Bearer $KEY" \
  $BASE/api/v1/jobs/$JOB_ID/cancel/ | python -m json.tool
```

### 9. Delete a job

```bash
curl -s -X DELETE -H "Authorization: Bearer $KEY" \
  $BASE/api/v1/jobs/$JOB_ID/ | python -m json.tool
```

---

## Python Example

A minimal end-to-end script using only the standard library:

```python
import json
import time
import urllib.request

BASE = "http://localhost:8000"
KEY = "your-api-key-here"


def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    headers = {"Authorization": f"Bearer {KEY}"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# Submit a job
result = api("POST", "/api/v1/jobs/", {
    "model": "boltz2",
    "name": "api test",
    "sequences": ">A\nMKTAYIAKQRQISFVKSHFSRQLEEISGC",
})
job_id = result["job"]["id"]
print(f"Submitted: {job_id}")

# Poll until done
while True:
    detail = api("GET", f"/api/v1/jobs/{job_id}/")
    status = detail["job"]["status"]
    print(f"Status: {status}")
    if status in ("COMPLETED", "FAILED"):
        break
    time.sleep(30)

# Download outputs
for f in detail["job"]["output_files"]:
    print(f"Downloading {f['name']}...")
    req = urllib.request.Request(
        f"{BASE}/api/v1/jobs/{job_id}/download/{f['name']}",
        headers={"Authorization": f"Bearer {KEY}"},
    )
    with urllib.request.urlopen(req) as resp:
        with open(f["name"], "wb") as fh:
            fh.write(resp.read())

print("Done.")
```

---

## Status Codes Summary

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Job created |
| 400 | Validation error or bad request |
| 401 | Authentication failed (missing, invalid, or revoked key) |
| 403 | Forbidden (inactive account or API access not enabled) |
| 404 | Job or file not found |
| 405 | HTTP method not allowed |
| 500 | Server error |
