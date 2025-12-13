# fold-webapp

Streamlit webapp for running AlphaFold3 jobs (and structured to support additional models later).

## Run

- Existing entrypoint (kept for compatibility):

```bash
streamlit run af3_web_app.py
```

- Package entrypoint:

```bash
streamlit run src/fold_webapp/main.py
```

## Configuration

Configuration is read from environment variables prefixed with `FOLD_` (optionally via a local `.env` file).

See `.env.example` for available settings.

## Initial setup (auth + database)

This app uses:

- GitHub OAuth for normal users (invite-only).
- Local username/password for a small number of admin accounts (offline fallback).
- A database (SQLite by default) to store users and job ownership.

### 1) Configure environment variables

At minimum, set these (via `.env` or your environment):

```bash
# Database
FOLD_DATABASE_URL=sqlite:////absolute/path/to/fold_webapp.db

# GitHub OAuth (create an OAuth App in GitHub)
FOLD_OAUTH_CLIENT_ID=your_github_client_id
FOLD_OAUTH_CLIENT_SECRET=your_github_client_secret
FOLD_OAUTH_REDIRECT_URI=http://your-host:8501
```

### 2) Initialize the database schema

Run Alembic migrations:

```bash
python scripts/init_db.py
```

### 3) Create the first local admin account (offline fallback)

This creates a local admin account that can sign in even if GitHub is unreachable:

```bash
python scripts/create_admin.py
```

### 4) Invite users

After logging in as an admin:

- Open the **Admin console** from the sidebar.
- Use **Invite user (GitHub)** to add a user’s GitHub username (invite-only).
- Invited users can then sign in with GitHub and will only see their own jobs/results.
