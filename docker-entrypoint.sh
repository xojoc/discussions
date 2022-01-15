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
#  --without-mingle --without-heartbeat --without-gossip
celery -A discussions worker --without-mingle --without-heartbeat --without-gossip -E -l WARNING -P gevent -c 50 &

echo "Run Celery Beat"
celery -A discussions beat -l WARNING &

echo "Run Huey consumer"
python manage.py run_huey


port=$1
if [ -z "$port" ]
then
   port="80"
fi

# until timeout 3 celery -A discussions inspect ping; do
#     >&2 echo "Celery workers not available"
# done

echo "Starting Flower"
celery -A discussions flower&

echo "Starting server on port $port"
if [ "$DJANGO_DEVELOPMENT" == "true" ]; then
	python manage.py runserver 0.0.0.0:$port &
else
	daphne --http-timeout 300 -v 0 -b 0.0.0.0 -p $port  discussions.asgi:application &
fi
echo "Now wait..."

wait
