SHELL = /bin/bash -o pipefail
include .env
export

poetry_export:
# Disable hashes for now since the installation of pycparser fails.
# Reenable them in the future.
	@poetry export --without-hashes  -f requirements.txt --output requirements.txt

deploy: poetry_export
	@git add requirements.txt
	-git commit -m "Update requirements.txt" -- requirements.txt
	@caprover deploy --default

run:
	echo $$DATABASE_HOST
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	-kill $$(lsof -i:5555 -t -sTCP:LISTEN)
	-kill $$(cat /var/run/celery/*.pid)
	-killall -KILL celery
	@poetry run ./docker-entrypoint.sh 7777

cp: lint test poetry_export
	@git add web/migrations
	@git commit -a
#@poetry export -f requirements.txt --output requirements.txt
#@git add requirements.txt
#-git commit -m "Update requirements.txt" -- requirements.txt
	@git push origin main

migrate:
	@poetry run python manage.py makemigrations
	@poetry run python manage.py migrate

d: poetry_export
#	@poetry self update
	@docker build -t discussions .
	-docker stop $$(docker ps -a -q)
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	-kill $$(lsof -i:5555 -t -sTCP:LISTEN)
	@docker run --rm --name discussions --env-file .env -dp 7777:80 -dp 5555:5555 discussions
	@docker logs -f $$(docker ps -l -f name=discussions --format '{{.ID}}')

dshell:
	docker exec -it $$(docker ps -l -f name=discussions -q) bash

shell:
	poetry run python manage.py shell

lint:
	@poetry run flake8 --extend-ignore E501,E741,E203 | tac
	# @poetry run mypy --install-types --non-interactive .

test:
	@echo 'tests skipped'
	# @poetry run python -Wa manage.py test --shuffle --noinput --keepdb


account:
	# poetry run python manage.py makemigrations web
	# poetry run python manage.py migrate web

	poetry run python manage.py migrate socialaccount zero
	poetry run python manage.py migrate admin zero
	poetry run python manage.py migrate sessions zero
	poetry run python manage.py migrate contenttypes zero
	poetry run python manage.py migrate auth zero
	# poetry run python manage.py makemigrations auth
	# poetry run python manage.py migrate auth
	poetry run python manage.py showmigrations


superuser:
	poetry run python manage.py createsuperuser