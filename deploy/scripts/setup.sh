#!/usr/bin/env bash
set -euo pipefail

# Проверка, что скрипт запущен от имени root
if [[ "${EUID}" -ne 0 ]]; then
  echo "Этот скрипт должен быть запущен от имени root (используйте sudo)"
  exit 1
fi

echo "=== Универсальная настройка развертывания Patent Generator ==="

# 1. Сбор данных от пользователя
read -p "Введите ваше доменное имя (например, patent.example.com): " DOMAIN_NAME
if [[ -z "$DOMAIN_NAME" ]]; then
    echo "Доменное имя обязательно для заполнения."
    exit 1
fi

read -p "Введите ваш email для SSL (Certbot): " SSL_EMAIL
if [[ -z "$SSL_EMAIL" ]]; then
    echo "Email обязателен для заполнения."
    exit 1
fi

DEFAULT_PROJECT_DIR=$(pwd)
read -p "Введите директорию проекта [$DEFAULT_PROJECT_DIR]: " PROJECT_DIR
PROJECT_DIR=${PROJECT_DIR:-$DEFAULT_PROJECT_DIR}

echo "--------------------------------------------------"
echo "Домен: $DOMAIN_NAME"
echo "Email:  $SSL_EMAIL"
echo "Путь:   $PROJECT_DIR"
echo "--------------------------------------------------"

# 2. Установка системных зависимостей
echo "Установка системных зависимостей..."
bash "$PROJECT_DIR/deploy/scripts/server_setup_root_docker.sh"

# 3. Генерация конфигурации Nginx
echo "Генерация конфигурации Nginx..."
CONF_PATH="$PROJECT_DIR/deploy/nginx/$DOMAIN_NAME.conf"
sed "s/{{DOMAIN_NAME}}/$DOMAIN_NAME/g" "$PROJECT_DIR/deploy/nginx/nginx.template.conf" > "$CONF_PATH"

echo "Применение конфигурации Nginx..."
ln -sf "$CONF_PATH" "/etc/nginx/sites-available/$DOMAIN_NAME"
ln -sf "/etc/nginx/sites-available/$DOMAIN_NAME" "/etc/nginx/sites-enabled/$DOMAIN_NAME"
rm -f /etc/nginx/sites-enabled/default

if nginx -t; then
    systemctl reload nginx
    echo "Nginx успешно настроен."
else
    echo "Ошибка проверки конфигурации Nginx. Пожалуйста, проверьте логи."
    exit 1
fi

# 4. Запуск Docker контейнеров
echo "Запуск Docker контейнеров..."
bash "$PROJECT_DIR/deploy/scripts/server_run_docker.sh" "$PROJECT_DIR"

# 5. Настройка SSL
read -p "Хотите настроить SSL с помощью Certbot сейчас? (y/n): " SETUP_SSL
if [[ "$SETUP_SSL" =~ ^[YyДд]$ ]]; then
    echo "Запуск Certbot..."
    certbot --nginx -d "$DOMAIN_NAME" --agree-tos -m "$SSL_EMAIL" --redirect -n
    echo "Настройка SSL завершена."
else
    echo "Пропуск настройки SSL. Вы можете запустить её позже вручную."
fi

echo "=================================================="
echo "Настройка успешно завершена!"
echo "Ваше приложение должно быть доступно по адресу: http://$DOMAIN_NAME (или https, если был включен SSL)"
echo "=================================================="
