deploy:
	@poetry export -f requirements.txt --output requirements.txt
	@git add requirements.txt
	@git commit -m "Update requirements.txt" -- requirements.txt
	@caprover deploy --default
