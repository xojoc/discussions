#!/bin/bash

echo "Collect static files"
#python manage.py collectstatic --noinput


echo "Apply database migrations"
python manage.py migrate --noinput

echo "Run Celery"
celery -A discussions worker -l info -P eventlet -c 500 -D

echo "Run Celery Beat"
celery -A discussions  beat -l info --detach

echo "Starting server"
python manage.py runserver 0.0.0.0:80
