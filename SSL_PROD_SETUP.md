# SSL Production Setup (Let's Encrypt + Certbot Docker)

This guide enables HTTPS for:

- `acp.id.vn`
- `www.acp.id.vn` (redirected to `acp.id.vn`)

## 1) Prerequisites

- DNS `A` records:
  - `@` -> `103.82.192.43`
  - `www` -> `103.82.192.43`
- Ports `80` and `443` are open on the server firewall/security group.
- No other service is binding host ports `80/443`.

## 2) Start production stack in bootstrap mode

Bootstrap mode serves HTTP and ACME challenge path so Certbot can issue certificates.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The default bootstrap config is:

- `nginx/prod.reverse-proxy.bootstrap.conf`

## 3) Issue certificates (one-shot)

```bash
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d acp.id.vn -d www.acp.id.vn \
  --email duychien25102004@gmail.com \
  --agree-tos --no-eff-email
```

## 4) Switch nginx to TLS config

Use the TLS nginx config by setting `NGINX_PROXY_CONF`:

```bash
NGINX_PROXY_CONF=prod.reverse-proxy.ssl.conf \
docker compose -f docker-compose.prod.yml up -d nginx
```

Then reload full stack (optional but recommended after first setup):

```bash
NGINX_PROXY_CONF=prod.reverse-proxy.ssl.conf \
docker compose -f docker-compose.prod.yml up -d
```

## 5) Verify HTTPS

- `http://acp.id.vn` -> `301` to `https://acp.id.vn`
- `http://www.acp.id.vn` -> `301` to `https://acp.id.vn`
- `https://www.acp.id.vn` -> `301` to `https://acp.id.vn`
- `https://acp.id.vn` loads frontend and `/api/v1` works.

## 6) Auto-renew certificates

Create cron on the host (example: every day at 03:15):

```cron
15 3 * * * cd /home/Agent-Content-Planner && docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot && NGINX_PROXY_CONF=prod.reverse-proxy.ssl.conf docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload >> /var/log/certbot-renew.log 2>&1
```

## 7) Dry-run renewal test

```bash
docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run --webroot -w /var/www/certbot
```

