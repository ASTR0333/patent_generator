# patent_generator

Генератор патентной документации для программ ЭВМ.

## Структура проекта

```
patent-generator/
├── generator.py    # Основная программа (CLI)
├── gui.py    # Tkinter GUI (устаревший)
├── backend/
│   └──  main.py    # FastAPI бэкенд
│   
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── AuthorForm.jsx    # Форма автора с валидацией и подсказками
│           └── FileUpload.jsx    # Компонент загрузки файлов
├── templates/    # Шаблоны .docx
├──  output/    # Папка для архива с результатами
└── requirements.txt     # Зависимости бэкенда
```

## Запуск веб-интерфейса

### 1. Бэкенд (FastAPI)

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск (из корня проекта)
uvicorn backend.main:app --reload --port 8000
```

Бэкенд будет доступен по адресу: http://localhost:8000

API документация (Swagger): http://localhost:8000/docs

### 2. Фронтенд (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Фронтенд будет доступен по адресу: http://localhost:5173

## Поддерживаемые форматы исходного кода

Помимо `.py`, теперь поддерживаются все популярные языки программирования:
`.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.cs`, `.go`,
`.rs`, `.rb`, `.php`, `.swift`, `.kt`, `.scala`, `.lua`, `.sh`, `.bash`, `.sql`,
`.html`, `.css`, `.scss`, `.json`, `.yaml`, `.toml`, `.dart`, и многие другие.

А также специальные имена файлов: `Dockerfile`, `Makefile`, `Gemfile`, и т.д.

## Поддержка архивов

При загрузке исходного кода можно прикрепить архив:
`.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.rar`, `.7z`

Архив автоматически распаковывается, из него извлекаются все файлы с исходным кодом,
которые последовательно вставляются в документ с разделителями (именами файлов).

## CLI запуск

```bash
pip install -r requirements.txt
python generator.py
```

> **Примечание:** Подсчёт страниц Word-документов (`pywin32`) работает только на Windows.
> На других платформах количество страниц будет отображаться как `?`.

