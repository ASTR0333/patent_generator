# Deployment Guide (Docker + Redis)

## 1) Локально: Docker Desktop

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

## 2) Универсальный скрипт установки (Ubuntu/Debian)

Самый быстрый способ развернуть проект на свежем сервере:

```bash
cd /opt
# если репозиторий еще не склонирован:
git clone <YOUR_REPO_URL> patent_generator
cd patent_generator
sudo bash deploy/scripts/setup.sh
```

Скрипт сам:
1. Запросит домен и email.
2. Установит Docker, Nginx, Certbot.
3. Сгенерирует и активирует конфиг Nginx в `deploy/nginx/your-domain.conf`.
4. Запустит Docker-контейнеры.
5. Предложит выпустить SSL сертификат.

## 3) Ручное управление (Docker)

Если вы хотите выполнить шаги по отдельности:

### 3.1 Установка системных зависимостей
```bash
sudo bash deploy/scripts/server_setup_root_docker.sh
```

### 3.2 Запуск Docker-стека
```bash
bash deploy/scripts/server_run_docker.sh /opt/patent_generator
```

### 3.3 Генерация Nginx конфига
Вы можете использовать `deploy/nginx/nginx.template.conf` как основу.

### 3.4 SSL Certbot
```bash
sudo certbot --nginx -d your-domain.com --agree-tos -m admin@example.com --redirect -n
```

## 4) Обновление в проде

```bash
cd /opt/patent_generator
git pull
docker compose -f docker-compose.server.yml up --build -d
sudo systemctl reload nginx
```

## 5) Диагностика

Статус:
```bash
docker compose -f docker-compose.server.yml ps
systemctl status nginx
```

Логи:
```bash
docker compose -f docker-compose.server.yml logs -f backend
docker compose -f docker-compose.server.yml logs -f frontend
docker compose -f docker-compose.server.yml logs -f redis
```

## 6) Порты/безопасность

Открыть снаружи только:
- `22/tcp` (SSH)
- `80/tcp` (HTTP)
- `443/tcp` (HTTPS)

Внутренние порты (`8000`, `4173`, `6379`) доступны только локально.

