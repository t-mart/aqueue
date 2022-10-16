ALL: format

.PHONY: format docs watch-docs

docs:
	sphinx-build docs/ docs-build/

watch-docs:
	sphinx-autobuild docs/ docs-build/ --watch src/ --watch examples/

format:
	isort src/ examples/
	black src/ examples/
