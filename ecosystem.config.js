module.exports = {
  apps: [
    {
      // Optional: PM2 config for non-Docker deployments.
      // This repo’s supported dev workflow is Docker Compose; keep this file as an example only.
      name: 'ph-eye-api',
      script: 'uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'ph-eye-worker',
      script: 'celery',
      args: '-A app.workers.celery_app:celery worker -l info -n worker1@%h -c 4 -Ofair',
      cwd: './backend',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'ph-eye-beat',
      script: 'celery',
      args: '-A app.workers.celery_app:celery beat --loglevel=info',
      cwd: './backend',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production'
      }
    }
  ]
};
