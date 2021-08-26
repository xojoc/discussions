#!/bin/bash

cleanup() {
  echo "Cleanup"
}

echo 'Set Trap'
trap 'trap " " SIGTERM; kill 0; wait; cleanup' SIGINT SIGTERM

echo "The script pid is $$"


#echo "Check production settings"
#python manage.py check --deploy


echo "Collect static files"
python manage.py collectstatic --noinput

echo "Apply database migrations"
python manage.py migrate --noinput

echo "Run Celery"
celery -A discussions worker -l WARNING -P gevent -c 500 &

echo "Run Celery Beat"
celery -A discussions beat -l WARNING &

port=$1
if [ -z "$port" ]
then
   port="80"
fi

echo "Starting Flower"
celery flower -A discussions&

echo "Starting server on port $port"
if [ "$DJANGO_DEVELOPMENT" == "true" ]; then
	python manage.py runserver 0.0.0.0:$port &
else
	daphne -v 0 -b 0.0.0.0 -p $port  discussions.asgi:application &
fi
echo "Now wait..."

wait
