# Changelog

Все значимые изменения в проекте документируются в этом файле.

## [Unreleased]

### Добавлено
- ✅ Миграция данных на JSON формат
- ✅ Модуль `content_manager.py` для загрузки JSON
- ✅ Структура папок `data/A1/1/vocabulary/` и `data/A1/1/grammar/`
- ✅ Метаданные в `metadata.json`
- ✅ Теория для грамматических тем
- ✅ Переводы примеров (`example_ru`)
- ✅ Немецкие названия категорий (`name_de`)
- ✅ Документация: `CONTENT_GUIDE.md`
- ✅ Сохранение прогресса по культуре и упражнениям в БД: таблицы `culture_progress`, `exercises_progress`; API `POST /api/progress/culture`, `POST /api/progress/exercise`; вызовы из Web App при просмотре темы, завершении викторины и набора упражнений.

### Изменено
- 🔄 `bot/handlers/flashcards.py` — использует `content_manager`
- 🔄 `bot/handlers/grammar.py` — использует `content_manager`
- 🔄 `bot/main.py` — инициализация контента при запуске
- 🔄 `web_server.py` — инициализация контента
- 🔄 `README.md` — обновлена структура проекта
- 🔄 `WEB_APP_SETUP.md` — обновлена структура

### Планируется
- 🔜 Модуль `pronunciation.py` для проверки произношения

## [1.1.0] - 2025-03-01

### Добавлено
- **Разделы «Культура» и «Упражнения»** для уровня A1.1 в Web App и API.
- **Culture:** 5 тем в `data/A1/1/culture/`: Du/Sie, еда и напитки, транспорт, магазины, пунктуальность. Формат: `content` (title, text, facts, tips), опционально `questions` для мини-викторины.
- **Exercises:** 3 набора в `data/A1/1/exercises/`: «Еда и кафе» (6 заданий), «Артикли и аккузатив» (7), «Базовые фразы» (5). Тип заданий: `multiple_choice` (question, options, correct, explanation).
- В **content_manager:** кэш `culture` и `exercises`, загрузка `_load_all_culture()` / `_load_all_exercises()`, API: `get_culture_topics`, `get_culture_topic`, `get_exercise_sets`, `get_exercise_set`, `get_exercise_tasks`.
- **API:** `GET /api/culture/topics`, `GET /api/culture/<topic_id>`, `GET /api/exercises/sets`, `GET /api/exercises/<set_id>`, `GET /api/exercises/<set_id>/tasks` (уровень через `?major=&sub=`).
- **Web App:** плитки «Культура» и «Упражнения» в главном меню; экран темы культуры (текст, факты, советы + до 2 вопросов викторины); пошаговое выполнение упражнений (вопрос → варианты → проверка → объяснение → «Далее»). Прогресс по культуре/упражнениям сохраняется (реализовано в следующем релизе).
- **Метаданные A1.1:** в `metadata.json` заполнены `content.culture` и `content.exercises` (topics/sets), статус `active`.
- **Контент A1.2:** папка `data/A1/2/` с диалогами, фразами, словарём, грамматикой, метаданными (в т.ч. greetings, restaurant, расширенные категории).
- **Скрипт** `scripts/generate_phrases_dialogues.py` для генерации фраз и диалогов.

### Изменено
- `bot/content_manager.py` — добавлены culture и exercises в кэш уровня, загрузка и публичный API; в `init_content()` и `init_all_levels()` подключена загрузка culture и exercises.
- `web_server.py` — импорты и маршруты для culture и exercises; в HTML-шаблоне добавлены секции и JS для культуры и упражнений.

## [1.0.0] - 2024-XX-XX

### Добавлено
- Базовая функциональность бота
- Карточки для изучения слов
- Грамматические тесты
- Аудио произношение (gTTS)
- Трекер прогресса
- Ежедневные напоминания
- Telegram Web App
- PostgreSQL поддержка

---

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).
