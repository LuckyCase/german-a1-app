# German A1 Telegram Bot

Telegram-бот для изучения немецкого языка уровня A1.

## Функции

- **Карточки (Flashcards)** - изучение слов с выбором перевода
- **Грамматические тесты** - тесты по темам A1 (артикли, глаголы, падежи)
- **Аудио произношение** - озвучка немецких слов через gTTS
- **Трекер прогресса** - статистика изучения
- **Ежедневные напоминания** - уведомления для практики

## Установка локально

1. Клонируйте репозиторий
2. Создайте виртуальное окружение:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Создайте файл `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token_from_botfather
   ```
5. Запустите бота:
   ```bash
   python -m bot.main
   ```

## Деплой на Render

1. Создайте репозиторий на GitHub и загрузите код
2. Зайдите на [render.com](https://render.com)
3. Создайте новый **Background Worker**
4. Подключите GitHub репозиторий
5. Настройте:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m bot.main`
6. Добавьте переменную окружения:
   - `TELEGRAM_BOT_TOKEN` = ваш токен от BotFather

## Команды бота

- `/start` - главное меню
- `/flashcards` - изучение слов
- `/grammar` - грамматические тесты
- `/progress` - ваша статистика
- `/reminder` - настройка напоминаний
- `/audio <текст>` - прослушать произношение
- `/help` - справка

## Структура проекта

```
TelegramBot/
├── bot/
│   ├── __init__.py
│   ├── config.py          # Конфигурация
│   ├── database.py        # Работа с SQLite
│   ├── main.py            # Точка входа
│   ├── data/
│   │   ├── vocabulary.py  # Словарь A1 (~200 слов)
│   │   └── grammar.py     # Грамматические тесты
│   └── handlers/
│       ├── common.py      # /start, /help
│       ├── flashcards.py  # Карточки
│       ├── grammar.py     # Тесты
│       ├── progress.py    # Статистика
│       ├── reminders.py   # Напоминания
│       └── audio.py       # Произношение
├── requirements.txt
├── Procfile
├── render.yaml
└── .env.example
```

## Контент

- ~200 слов по категориям (семья, еда, время, транспорт и др.)
- 8 грамматических тестов по темам A1
- Все слова с примерами использования
