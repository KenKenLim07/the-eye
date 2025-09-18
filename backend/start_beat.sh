#!/bin/bash

echo "🚀 SENIOR DEV BEAT SCHEDULER - Bulletproof Version"

# Clean up any corrupted BDB files (optional safety)
rm -f celerybeat-schedule.db*

# Start beat with no pidfile lock issues
exec celery -A app.workers.celery_app:celery beat \
    --loglevel=info \
    --scheduler=celery.beat:PersistentScheduler \
    --pidfile= \
    --logfile=/tmp/celerybeat.log \
    --max-interval=60
