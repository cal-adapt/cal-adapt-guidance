preview:
	quarto render --to html
	@echo "Browse at http://localhost:8080"
	cd _site && python -m http.server 8080
