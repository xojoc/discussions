deploy:
	@poetry export -f requirements.txt --output requirements.txt
	@git add requirements.txt
	-git commit -m "Update requirements.txt" -- requirements.txt
	@caprover deploy --default


run:
	-kill $$(lsof -i:7777 -t)
	@poetry run python3 manage.py runserver 7777&


cp:
	@git commit -a && git push
