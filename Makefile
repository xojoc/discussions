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
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	#@poetry run python3 manage.py runserver 7777&
	@poetry run ./docker-entrypoint.sh 7777

cp: lint test poetry_export
	@git commit -a
#@poetry export -f requirements.txt --output requirements.txt
#@git add requirements.txt
#-git commit -m "Update requirements.txt" -- requirements.txt
	@git push origin main

migrate:
	@poetry run python manage.py makemigrations web
	@poetry run python manage.py migrate

d: poetry_export
	@poetry self update
	@docker build -t discussions .
	-docker stop $$(docker ps -a -q)
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	@docker run --env-file .env -dp 7777:80 discussions

shell:
	poetry run python manage.py shell


lint:
	@poetry run flake8 --extend-ignore E501 | tac

test:
	@poetry run python -Wa manage.py test --noinput --keepdb
