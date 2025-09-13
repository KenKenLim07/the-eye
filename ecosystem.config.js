module.exports = {
  apps: [
    {
      name: 'ph-eye-api',
      script: '/Users/mac/ph-eye/backend/venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000',
      cwd: '/Users/mac/ph-eye/backend',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'ph-eye-worker',
      script: '/Users/mac/ph-eye/backend/venv/bin/celery',
      args: '-A app.celery worker --loglevel=info',
      cwd: '/Users/mac/ph-eye/backend',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'ph-eye-beat',
      script: '/Users/mac/ph-eye/backend/venv/bin/celery',
      args: '-A app.celery beat --loglevel=info',
      cwd: '/Users/mac/ph-eye/backend',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production'
      }
    }
  ]
};
