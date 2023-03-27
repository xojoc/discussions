SHELL = /bin/bash -o pipefail
include .env
export


poetry_export:
# Disable hashes for now since the installation of pycparser fails.

# Reenable them in the future.
# --without-hashes
	@poetry export   -f requirements.txt --output requirements.txt

sass_compile:
	@poetry run ./manage.py sass web/static/style.scss web/static/style.css

sass_watch:
	@poetry run ./manage.py sass web/static/style.scss web/static/style.css --watch

deploy: poetry_export sass_compile
	@git add requirements.txt
	-git commit -m "Update requirements.txt" -- requirements.txt
	@git add web/static/style.css
	-git commit -m "Update web/static/style.css" -- web/static/style.css
	@caprover deploy --default

run: sass_compile
	echo $$DATABASE_HOST
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	-kill $$(lsof -i:5555 -t -sTCP:LISTEN)
	-kill $$(cat /var/run/celery/*.pid)
	-killall -KILL celery
	-killall -KILL stripe
	stripe listen --forward-to localhost:7777/stripe/webhook/&
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

d: poetry_export sass_compile
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
	poetry run python manage.py shell_plus --bpython

lint:
	@poetry run flake8 --extend-ignore E501,E741,E203 | tac
	# @poetry run mypy --install-types --non-interactive .

test:
	@poetry run python -Wa manage.py test --shuffle --keepdb --failfast

utest:
	@poetry run python -Wa manage.py test --failfast -k 'Unit'

superuser:
	poetry run python manage.py createsuperuser

update:
	@poetry update
	@poetry types update