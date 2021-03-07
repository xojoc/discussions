#!/bin/bash

echo "Collect static files"
#python manage.py collectstatic --noinput


echo "Apply database migrations"
python manage.py migrate --noinput

echo "Run Celery"
celery multi start worker -A discussions -l info &

echo "Run Celery Beat"
celery -A discussions  beat -l info &

echo "Starting server"
python manage.py runserver 0.0.0.0:80
