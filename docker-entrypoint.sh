#!/bin/bash

cleanup() {
  echo "Cleanup"
}

echo 'Set Trap'
trap 'trap " " SIGTERM; kill 0; wait; cleanup' SIGINT SIGTERM

echo "The script pid is $$"

echo "Collect static files"
python manage.py collectstatic --noinput

echo "Apply database migrations"
python manage.py migrate --noinput

echo "Run Celery"
celery -A discussions worker -l warning -P gevent -c 500 &

echo "Run Celery Beat"
celery -A discussions beat -l warning &

port=$1
if [ -z "$port" ]
then
   port="80"
fi

echo "Starting server on port $port"
python manage.py runserver 0.0.0.0:$port &

wait
