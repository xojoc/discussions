deploy:
	@poetry export -f requirements.txt --output requirements.txt
	@git add requirements.txt
	-git commit -m "Update requirements.txt" -- requirements.txt
	@caprover deploy --default


run:
	@poetry run python3 manage.py runserver&


cp:
	@git commit -a && git push
