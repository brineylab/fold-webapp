# fold-webapp

Minimal intranet web UI for submitting protein structure prediction jobs to SLURM.

### Quick start (dev)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# optional: create a .env (see env.example)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Polling (cron)

Run the poller periodically (e.g. once per minute):

```bash
python manage.py poll_jobs
```

### Notes

- **Job directories**: controlled filesystem layout under `JOB_BASE_DIR/<job_uuid>/...` (default: `./job_data/`).
- **Fake mode**: set `FAKE_SLURM=1` to develop without SLURM; jobs will transition PENDING→RUNNING→COMPLETED automatically.