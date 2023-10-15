SHELL = /bin/bash -o pipefail
include .env
export

poetry_export:
	@poetry export -f requirements.txt --output requirements.txt

sass_compile:
	@poetry run ./manage.py sass web/static/style.scss web/static/style.css

sass_watch:
	@poetry run ./manage.py sass web/static/style.scss web/static/style.css --watch

.SILENT: run
run: sass_compile
	-@kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	#-@kill $$(lsof -i:5555 -t -sTCP:LISTEN)
	#-@kill $$(cat /var/run/celery/*.pid)
	#-@killall -KILL celery
	#-@killall -KILL stripe
	#@stripe listen --forward-to localhost:7777/stripe/webhook/&
	@poetry run ./docker-entrypoint.sh -p 7777 -c

debug: sass_compile 
	@poetry run ./docker-entrypoint.sh -d -p 7777 

run-celery:
	@poetry run celery -A discussions worker -l info

pre-commit: sass_compile lint test poetry_export
	@git add web/static/style.css
	@git add requirements.txt
	@git add web/migrations

cp:
	@git commit -a
	@git push origin main
	@git status 

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
	@echo 'Listening on port 7777...'
	@docker logs -f $$(docker ps -l -f name=discussions --format '{{.ID}}')

dshell:
	docker exec -it $$(docker ps -l -f name=discussions -q) bash

shell:
	# poetry run python manage.py shell_plus --bpython
	poetry run python manage.py shell

lint:
	# @poetry run deptry .
	# @poetry run pyright .
	# @poetry run ruff check . | tac
	# @poetry run flake8 --extend-ignore E501,E741,E203 | tac
	# @poetry run mypy --install-types --non-interactive .

test:
	@poetry run python -Wa manage.py test --pdb --shuffle --keepdb --failfast -v 2

utest:
	# @poetry run python -m unittest discover -s web -p '*.py' -t .
	@poetry run python -Wa manage.py test --pdb --shuffle --keepdb --failfast -k 'Unit' -v 2

superuser:
	poetry run python manage.py createsuperuser

update:
	@poetry update
	@poetry types update


extension-build:
	cd browser-extension-v3; web-ext build --overwrite-dest
	cd browser-extension; web-ext build --overwrite-dest


get-twitter-token:
	twurl authorize --consumer-key ${TWITTER_CONSUMER_KEY} --consumer-secret ${TWITTER_CONSUMER_SECRET}
