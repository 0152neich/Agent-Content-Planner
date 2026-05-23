# production nginx proxy config (SSL)
PROD_NGINX_PROXY_CONF ?= prod.reverse-proxy.ssl.conf

# development environment
dev:
	docker compose -f docker-compose.dev.yml up --build

# production environment
prod:
	NGINX_PROXY_CONF=$(PROD_NGINX_PROXY_CONF) docker compose -f docker-compose.prod.yml up --build -d

# stop all environments
down:
	docker compose -f docker-compose.dev.yml down
	docker compose -f docker-compose.prod.yml down

# delete all containers and volumes
delete:
	docker compose -f docker-compose.dev.yml down -v --rmi all
	docker compose -f docker-compose.prod.yml down -v --rmi all

# view logs
logs:
	docker compose -f docker-compose.prod.yml logs -f

# restart production environment
restart:
	docker compose -f docker-compose.prod.yml restart
