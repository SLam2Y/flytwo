include .env

SRC_DIR := src

migration:
	alembic revision --autogenerate

migrate:
	alembic upgrade head

set_hook:
	curl --request POST --url https://api.telegram.org/bot${BOT_TOKEN}/setWebhook --header 'content-type: application/json' --data '{"url": "${API_URL}/webhook", "secret_token": "${TG_SECRET}"}'

delete_hook:
	curl --request POST --url 'https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook'

set_profile:
	PYTHONPATH=$(SRC_DIR) uv run python -c 'import asyncio; from bot.bot import setup_profile; asyncio.run(setup_profile())'

test:
	uv run pytest -n 1 tests

# This is a phony target, meaning it doesn't represent a file
.PHONY: migration migrate set_hook delete_hook set_profile test
