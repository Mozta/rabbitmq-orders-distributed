.PHONY: dev staging prod down logs

dev:
	docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up --build

staging:
	docker compose --env-file .env.staging -f docker-compose.yml -f docker-compose.staging.yml up --build

prod:
	docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build

down:
	docker compose down -v

logs:
	docker compose logs -f
