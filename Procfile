# Development process definitions (use with honcho)
# Install: pip install honcho
# Run: honcho start

web: python manage.py runserver 0.0.0.0:8000
poller: sh -c 'while true; do python manage.py poll_jobs; sleep 10; done'

