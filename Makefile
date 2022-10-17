ALL: format

.PHONY: format docs watch-docs

docs:
	sphinx-build -n docs/ docs-build/

watch-docs:
	sphinx-autobuild -n docs/ docs-build/ --watch src/ --watch examples/

format:
	isort src/ examples/
	black src/ examples/
