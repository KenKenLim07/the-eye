#!/bin/bash

echo "🚀 SENIOR DEV BEAT SCHEDULER - Bulletproof Version"

# Clean up any corrupted BDB files
rm -f celerybeat-schedule.db*

# Start beat with proper error handling and no lock issues
exec celery -A app.workers.celery_app:celery beat \
    --loglevel=info \
    --scheduler=celery.beat:PersistentScheduler \
    --pidfile=/tmp/celerybeat.pid \
    --logfile=/tmp/celerybeat.log \
    --max-interval=60
