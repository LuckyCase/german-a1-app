# AGENTS.md — контекст для AI-агентов

Telegram-бот для изучения немецкого языка уровня A1 (Goethe-Institut). Веб-интерфейс через Telegram Web App, бэкенд на Python.

## Стек и окружение

- **Python 3.10+**
- **python-telegram-bot** (Webhook + polling), **Flask** (Web App + webhook endpoint), **asyncpg** (PostgreSQL), **gTTS** (аудио), **JSON** (учебный контент)
- Локально: виртуальное окружение, `.env` с `TELEGRAM_BOT_TOKEN`, опционально `DATABASE_URL` (если пусто — SQLite)
- Зависимости: `pip install -r requirements.txt`

## Запуск

```bash
# Только бот (polling)
python -m bot.main

# Web App + Webhook (два процесса или один web_server)
python web_server.py
# при необходимости отдельно: python -m bot.main
```

Инициализация БД (опционально):  
`python -c "import asyncio; from bot.database import init_db; asyncio.run(init_db())"`

## Структура кода

| Путь | Назначение |
|------|------------|
| `bot/main.py` | Точка входа, регистрация handlers |
| `bot/config.py` | Конфиг из env (токен, DATABASE_URL, WEB_APP_URL) |
| `bot/database.py` | Инициализация БД, asyncpg/SQLite |
| `bot/content_manager.py` | Загрузка и кэш данных из `data/A1/` (JSON) |
| `bot/handlers/` | Обработчики: `common`, `flashcards`, `grammar`, `progress`, `reminders`, `audio`, `feedback` |
| `web_server.py` | Flask: Web App (index), webhook, health, setup-webhook |
| `data/A1/` | Учебные данные: `vocabulary/`, `grammar/`, `phrases/`, `dialogues/` (JSON) |

Контент читается через `content_manager`; файлы в `bot/data/` (vocabulary.py, grammar.py) устарели — не опираться на них.

## Конвенции при правках

- **Язык кода и комментариев**: по желанию русский или английский; строки для пользователя (кнопки, сообщения) — на русском.
- **Handlers**: один модуль на фичу в `bot/handlers/`, обработчики регистрируются в `bot/main.py`. Callback-паттерны задаются в `CallbackQueryHandler(..., pattern="^...")`.
- **Новый контент**: только в `data/A1/` в формате JSON. Схемы и примеры — в `CONTENT_GUIDE.md` и `README.md`. После изменения JSON перезапуск или вызов `reload_content()`.
- **БД**: миграции не используются; изменения схемы — в `bot/database.py` с учётом существующих данных.
- **Стиль**: обычный Python (типизация по возможности, без лишних абстракций).

## Полезные файлы

- **README.md** — установка, деплой (Render), структура проекта, описание фич.
- **CONTENT_GUIDE.md** — как добавлять/редактировать словарь, грамматику, фразы, диалоги (форматы JSON).
- **.env.example** — пример переменных окружения.

## Тесты и деплой

- Явных тестов в репозитории нет; при добавлении — предпочтительно pytest в корне или в `tests/`.
- Деплой: Render (Web Service для Web App), см. `render.yaml`, `Procfile`, раздел «Деплой» в README.

При добавлении фич или контента сохранять совместимость с текущей структурой `data/A1/` и списком handlers в `main.py`.
