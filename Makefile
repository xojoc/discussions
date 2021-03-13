SHELL = /bin/bash -o pipefail
include .env
export


deploy:
	@poetry export -f requirements.txt --output requirements.txt
	@git add requirements.txt
	-git commit -m "Update requirements.txt" -- requirements.txt
	@caprover deploy --default


run:
	-kill $$(lsof -i:7777 -t -sTCP:LISTEN)
	@poetry run python3 manage.py runserver 7777&


cp: lint test
	@git commit -a && git push

migrate:
	@poetry run python manage.py makemigrations web
	@poetry run python manage.py migrate

d:
	@poetry export -f requirements.txt --output requirements.txt
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
