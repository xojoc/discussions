#!/bin/bash

cleanup() {
	echo "Cleanup"
}

trap 'trap " " SIGTERM; kill 0; wait; cleanup' SIGINT SIGTERM
echo "The script pid is $$"

celery=false
debug=false
port="80"

while getopts 'cdp:' option; do
	case "${option}" in
	c)
		celery=true
		;;
	d)
		debug=true
		;;
	p)
		port="${OPTARG}"
		;;
	*)
		echo 'Unknown option "${option}"'
		exit 1
		;;
	esac
done

#echo "Check production settings"
#python manage.py check --deploy

if [ "$DJANGO_DEVELOPMENT" == "true" ]; then
	echo 'nop' >/dev/null
else
	echo "Collect static files"
	python manage.py collectstatic --noinput

	echo "Apply database migrations"
	python manage.py migrate --noinput

	echo "Run Celery"
	#  --without-mingle --without-heartbeat --without-gossip
	#celery -A discussions multi start 4 --without-mingle --without-heartbeat --without-gossip -E -l info -P gevent -c 50 &
	celery -A discussions worker -n celery_cpu_1@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	celery -A discussions worker -n celery_cpu_2@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	celery -A discussions worker -n celery_cpu_3@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	celery -A discussions worker -n celery_cpu_4@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	#celery -A discussions worker --without-mingle --without-heartbeat --without-gossip -E -l info -P prefork &

	echo "Run Celery Beat"
	celery -A discussions beat -l WARNING &

	echo "Starting Flower"
	celery -A discussions flower &
fi

echo "Starting server on port $port"
if [ "$DJANGO_DEVELOPMENT" == "true" ]; then
	python manage.py runserver 0.0.0.0:"$port" &
else
	daphne --http-timeout 300 -v 0 -b 0.0.0.0 -p "$port" discussions.asgi:application &
fi
echo "Now wait..."

wait
