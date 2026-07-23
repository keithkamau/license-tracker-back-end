#!/bin/bash

set -e

echo "Creating necessary directories..."
mkdir -p /app/logs
mkdir -p /app/staticfiles
mkdir -p /app/media

echo "Waiting for PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "PostgreSQL started"

echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "Redis started"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Creating superuser if not exists..."
python manage.py shell -c "
from accounts.models import User;
User.objects.filter(email='admin@example.com').exists() or \
User.objects.create_superuser('admin@example.com', 'Admin123!', first_name='Admin', last_name='User')
"

echo "Starting application..."
exec "$@"