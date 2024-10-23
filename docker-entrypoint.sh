#!/bin/bash

cleanup() {
	echo "Cleanup"
}

trap 'trap " " SIGTERM; kill 0; wait; cleanup' SIGINT SIGTERM
echo "The script pid is $$"

celery=false
debug=false
port="80"
celery_processes=16
celery_threads=16

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
		echo "Unknown option '${option}'"
		exit 1
		;;
	esac
done

#echo "Check production settings"
#python manage.py check --deploy

if [ "$DJANGO_DEVELOPMENT" == "true" ]; then 
	celery_processes=2 
	celery_threads=2
fi

if [ "$DJANGO_DEVELOPMENT" != "true" ] || $celery; then
	echo "Apply database migrations"
	python manage.py migrate --noinput

	echo "Collect static files"
	python manage.py collectstatic --noinput

	echo "Run Celery"
	#  --without-mingle --without-heartbeat --without-gossip
	DJANGO_POOL_MIN_SIZE=3 DJANGO_POOL_MAX_SIZE=3 DJANGO_DB_APPLICATION_NAME="discu celery" celery -A discussions multi start "${celery_processes}" -c "${celery_threads}"  -E -l info -P threads \
               --pidfile="$HOME/run/celery/%n.pid" \
               --logfile="$HOME/log/celery/%n%I.log" &
	# celery -A discussions worker -n celery_cpu_1@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	# celery -A discussions worker -n celery_cpu_2@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	# celery -A discussions worker -n celery_cpu_3@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	# celery -A discussions worker -n celery_cpu_4@%h -E -l info -P gevent -c 50 --without-mingle --without-heartbeat --without-gossip &
	#celery -A discussions worker --without-mingle --without-heartbeat --without-gossip -E -l info -P prefork &

	echo "Run Celery Beat"
	DJANGO_POOL_MIN_SIZE=2 DJANGO_POOL_MAX_SIZE=2 DJANGO_DB_APPLICATION_NAME="discu celery beat" celery -A discussions beat -l WARNING &

	echo "Starting Flower"
	DJANGO_POOL_MIN_SIZE=2 DJANGO_POOL_MAX_SIZE=2 DJANGO_DB_APPLICATION_NAME="discu celery flower" celery -A discussions flower --basic-auth="${FLOWER_USER}:${FLOWER_PASSWORD}" &
fi

echo "Starting server on port $port"
if [ "$DJANGO_DEVELOPMENT" == "true" ]; then
	python manage.py runserver 0.0.0.0:"$port" &
else
	daphne --http-timeout 300 -v 0 -b 0.0.0.0 -p "$port" discussions.asgi:application &
fi
echo "Now wait..."

wait
