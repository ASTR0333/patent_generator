# Deployment Guide (Docker + Redis)

## 1) Локально: Docker Desktop (macOS)

### 1.1 Установка Docker
1. Установи Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Дождись статуса `Engine running`.

### 1.2 Запуск проекта
Из корня проекта:

```bash
docker compose up --build -d
```

Проверка:
- Сайт: http://localhost
- API: http://localhost/api/patterns
- Swagger backend: http://localhost:8000/docs

Остановка:

```bash
docker compose down
```

## 2) Сервер Ubuntu root: patent.ikb-mirea.ru (без screen, только Docker)

Дано:
- Домен: `patent.ikb-mirea.ru`
- IP: `138.124.241.169`

Архитектура:
- Docker stack: `frontend + backend + redis`
- frontend контейнер слушает `127.0.0.1:4173`
- backend контейнер слушает `127.0.0.1:8000`
- Nginx (хост) проксирует домен на эти localhost-порты
- TLS выдаёт Certbot

### 2.1 DNS
Проверь A-запись:
- `patent.ikb-mirea.ru -> 138.124.241.169`

### 2.2 SSH
```bash
ssh root@138.124.241.169
```

### 2.3 Установка Docker + Nginx + Certbot
```bash
cd /opt
# если репозиторий еще не склонирован:
# git clone <YOUR_REPO_URL> patent_generator
cd /opt/patent_generator
bash deploy/scripts/server_setup_root_docker.sh
```

### 2.4 Запуск Docker-стека
```bash
cd /opt/patent_generator
git pull
bash deploy/scripts/server_run_docker.sh /opt/patent_generator
```

Проверка контейнеров:
```bash
docker compose -f /opt/patent_generator/docker-compose.server.yml ps
```

### 2.5 Nginx reverse proxy
```bash
cp /opt/patent_generator/deploy/nginx/patent.ikb-mirea.ru.conf /etc/nginx/sites-available/patent.ikb-mirea.ru
ln -sf /etc/nginx/sites-available/patent.ikb-mirea.ru /etc/nginx/sites-enabled/patent.ikb-mirea.ru
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### 2.6 SSL Certbot
```bash
certbot --nginx -d patent.ikb-mirea.ru --agree-tos -m admin@ikb-mirea.ru --redirect -n
```

Проверка автопродления:
```bash
systemctl status certbot.timer
certbot renew --dry-run
```

## 3) Обновление в проде

```bash
ssh root@138.124.241.169
cd /opt/patent_generator
git pull
docker compose -f docker-compose.server.yml up --build -d
systemctl reload nginx
```

## 4) Диагностика

Статус:
```bash
docker compose -f /opt/patent_generator/docker-compose.server.yml ps
systemctl status nginx
```

Логи:
```bash
docker compose -f /opt/patent_generator/docker-compose.server.yml logs -f backend
docker compose -f /opt/patent_generator/docker-compose.server.yml logs -f frontend
docker compose -f /opt/patent_generator/docker-compose.server.yml logs -f redis
```

Проверки:
```bash
curl -I http://127.0.0.1:4173
curl -I http://127.0.0.1:8000/api/patterns
curl -I https://patent.ikb-mirea.ru
```

## 5) Порты/безопасность

Открыть снаружи только:
- `22/tcp` (SSH)
- `80/tcp` (HTTP)
- `443/tcp` (HTTPS)

Не открывать:
- `6379` (Redis)
- `8000` (backend)
- `4173` (frontend)

Они слушают только `127.0.0.1` в server-compose.

## 6) Legacy (если нужен старый режим screen)

Скрипты screen сохранены в `deploy/scripts/start_screen_services.sh`, но рекомендуемый прод-режим теперь только Docker.
