.PHONY: install dev build test lint up

install:
	pip install -e ".[all]"
	cd web && npm install && npm run build

dev:
	cd web && npm run dev

build:
	cd web && npm run build

test:
	pytest -q

lint:
	ruff check src tests

up:
	xplogent up
