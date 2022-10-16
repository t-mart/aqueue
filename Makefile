ALL: format

.PHONY: format
format:
	isort src/ examples/
	black src/ examples/
