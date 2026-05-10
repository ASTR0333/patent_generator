# patent_generator

Генератор патентной документации для программ ЭВМ.

## Архитектура

Проект состоит из 3 основных слоев:

1. Frontend (React + Vite + Tailwind + ReactQuill)
- Пошаговый сценарий (wizard):
  - приветственный экран;
  - ввод количества авторов;
  - ввод данных авторов + названия программы;
  - загрузка исходника/реферата + редактор текста реферата.
- Редактор реферата (Quill) с поддержкой заголовков, списков, цветов, выравнивания.
- Тема light/dark.
- API вызывается через относительный префикс `/api`.

2. Backend (FastAPI)
- Единый upload endpoint: `POST /api/upload` с `kind=source|referat`.
- Генерация документов:
  - `POST /api/generate` (синхронная);
  - `POST /api/generate-queued` + `GET /api/generate-status/{job_id}` (через очередь Redis).
- Сборка DOCX по шаблонам в `templates/`.
- Архив результатов `*_пакет_документов.zip` (без UUID в имени).
- Скачивание через `GET /api/download/{filename}` с красивым `Content-Disposition`.

3. Queue / Storage
- Redis используется как backend очереди:
  - список задач: `patent_generator:jobs:queue`;
  - статусы задач: `patent_generator:job:<job_id>`.
- `output/` используется для загруженных и сгенерированных файлов.
- Включена автоочистка `output`:
  - переменные: `OUTPUT_RETENTION_HOURS` (по умолчанию 72),
  - `OUTPUT_CLEANUP_INTERVAL_SECONDS` (по умолчанию 21600).

## Структура

```text
patent_generator/
├── backend/
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── components/
│   ├── package.json
│   └── vite.config.js
├── templates/
│   ├── referat.docx
│   ├── source_code_template.docx
│   └── pril*.docx
├── generator.py
├── requirements.txt
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── docker-compose.server.yml
├── .gitignore
└── .dockerignore
```

## Запуск без Docker (локально)

### 1) Backend

```bash
pip install -r requirements.txt
REDIS_URL=redis://localhost:6379/0 uvicorn backend.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## Запуск через Docker (локально)

```bash
docker compose up --build -d
```

Проверка:
- Сайт: http://localhost
- API: http://localhost/api/patterns
- Backend docs: http://localhost:8000/docs

Остановка:

```bash
docker compose down
```

## Запуск через Docker (сервер)

Для быстрого развертывания на удаленном сервере (Ubuntu/Debian) используйте универсальный скрипт:

```bash
sudo bash deploy/scripts/setup.sh
```

Подробную информацию о развертывании, настройке Nginx и SSL читайте в [deploy/README.md](deploy/README.md).

