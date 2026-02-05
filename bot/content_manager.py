"""
Content Manager - загрузка и управление учебными данными из JSON файлов.

Этот модуль обеспечивает:
- Загрузку словаря и грамматических тестов из JSON
- Кэширование данных для быстрого доступа
- Поддержку уровней: A1.1, A1.2, A2.1, A2.2, B1.1, B1.2, B2.1, B2.2, C1.1, C1.2, C2.1, C2.2
- Обратную совместимость с существующим API
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

# Базовый путь к папке с данными
BASE_DATA_DIR = Path(__file__).parent.parent / "data"

# Доступные уровни (major_level, sub_level)
AVAILABLE_LEVELS = [
    ("A1", "1"), ("A1", "2"),
    ("A2", "1"), ("A2", "2"),
    ("B1", "1"), ("B1", "2"),
    ("B2", "1"), ("B2", "2"),
    ("C1", "1"), ("C1", "2"),
    ("C2", "1"), ("C2", "2"),
]

# Текущий выбранный уровень (по умолчанию A1.1)
_current_level: tuple = ("A1", "1")

# Кэш для загруженных данных (ключ = level_key)
_cache: Dict[str, dict] = {}


def _get_level_key(major: str = None, sub: str = None) -> str:
    """Получить ключ для кэша на основе уровня."""
    if major is None:
        major, sub = _current_level
    return f"{major}_{sub}"


def _get_level_path(major: str = None, sub: str = None) -> Path:
    """Получить путь к папке уровня."""
    if major is None:
        major, sub = _current_level
    return BASE_DATA_DIR / major / sub


def _get_level_cache(major: str = None, sub: str = None) -> dict:
    """Получить или создать кэш для уровня."""
    key = _get_level_key(major, sub)
    if key not in _cache:
        _cache[key] = {
            "vocabulary": {},
            "grammar": {},
            "phrases": {},
            "dialogues": {},
            "metadata": None
        }
    return _cache[key]


# ============================================================
# Функции управления уровнями
# ============================================================

def set_level(major: str, sub: str) -> bool:
    """
    Установить текущий уровень.
    
    Args:
        major: Основной уровень (A1, A2, B1, B2, C1, C2)
        sub: Подуровень (1 или 2)
    
    Returns:
        True если уровень установлен успешно
    """
    global _current_level
    
    major = major.upper()
    sub = str(sub)
    
    if (major, sub) not in AVAILABLE_LEVELS:
        logger.error(f"Недопустимый уровень: {major}.{sub}")
        return False
    
    level_path = _get_level_path(major, sub)
    if not level_path.exists():
        logger.warning(f"Папка уровня не существует: {level_path}")
        # Не возвращаем False - уровень может быть пустым, но валидным
    
    _current_level = (major, sub)
    logger.info(f"Уровень установлен: {major}.{sub}")
    return True


def get_current_level() -> tuple:
    """Получить текущий уровень (major, sub)."""
    return _current_level


def get_current_level_str() -> str:
    """Получить текущий уровень в формате строки (например, 'A1.1')."""
    major, sub = _current_level
    return f"{major}.{sub}"


def get_available_levels() -> List[dict]:
    """
    Получить список доступных уровней с информацией о наличии контента.
    
    Returns:
        Список словарей с информацией об уровнях
    """
    levels = []
    for major, sub in AVAILABLE_LEVELS:
        level_path = _get_level_path(major, sub)
        has_content = level_path.exists() and any(level_path.iterdir()) if level_path.exists() else False
        
        levels.append({
            "major": major,
            "sub": sub,
            "name": f"{major}.{sub}",
            "display_name": f"Уровень {major}.{sub}",
            "has_content": has_content,
            "is_current": (major, sub) == _current_level
        })
    
    return levels


def get_levels_with_content() -> List[dict]:
    """Получить только уровни с контентом."""
    return [level for level in get_available_levels() if level["has_content"]]


# ============================================================
# Базовые функции загрузки
# ============================================================

def _load_json(filepath: Path) -> dict:
    """Загрузить JSON файл."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл не найден: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON {filepath}: {e}")
        return {}


def get_metadata(major: str = None, sub: str = None) -> dict:
    """Получить метаданные уровня."""
    cache = _get_level_cache(major, sub)
    if cache["metadata"] is None:
        level_path = _get_level_path(major, sub)
        cache["metadata"] = _load_json(level_path / "metadata.json")
    return cache["metadata"] or {}


def _load_all_vocabulary(major: str = None, sub: str = None) -> dict:
    """Загрузить все категории словаря для уровня."""
    cache = _get_level_cache(major, sub)
    
    if cache["vocabulary"]:
        return cache["vocabulary"]
    
    vocab_dir = _get_level_path(major, sub) / "vocabulary"
    if not vocab_dir.exists():
        logger.warning(f"Папка словаря не найдена: {vocab_dir}")
        return {}
    
    for json_file in vocab_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                cache["vocabulary"][data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(cache['vocabulary'])} категорий словаря для уровня {_get_level_key(major, sub)}")
    return cache["vocabulary"]


def _load_all_grammar(major: str = None, sub: str = None) -> dict:
    """Загрузить все грамматические тесты для уровня."""
    cache = _get_level_cache(major, sub)
    
    if cache["grammar"]:
        return cache["grammar"]
    
    grammar_dir = _get_level_path(major, sub) / "grammar"
    if not grammar_dir.exists():
        logger.warning(f"Папка грамматики не найдена: {grammar_dir}")
        return {}
    
    for json_file in grammar_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                cache["grammar"][data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(cache['grammar'])} грамматических тем для уровня {_get_level_key(major, sub)}")
    return cache["grammar"]


def _load_all_phrases(major: str = None, sub: str = None) -> dict:
    """Загрузить все категории фраз для уровня."""
    cache = _get_level_cache(major, sub)
    
    if cache["phrases"]:
        return cache["phrases"]
    
    phrases_dir = _get_level_path(major, sub) / "phrases"
    if not phrases_dir.exists():
        logger.warning(f"Папка phrases не найдена: {phrases_dir}")
        return {}
    
    for json_file in phrases_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                cache["phrases"][data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(cache['phrases'])} категорий phrases для уровня {_get_level_key(major, sub)}")
    return cache["phrases"]


def _load_all_dialogues(major: str = None, sub: str = None) -> dict:
    """Загрузить все диалоги для уровня."""
    cache = _get_level_cache(major, sub)
    
    if cache["dialogues"]:
        return cache["dialogues"]
    
    dialogues_dir = _get_level_path(major, sub) / "dialogues"
    if not dialogues_dir.exists():
        logger.warning(f"Папка dialogues не найдена: {dialogues_dir}")
        return {}
    
    for json_file in dialogues_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                cache["dialogues"][data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(cache['dialogues'])} диалогов для уровня {_get_level_key(major, sub)}")
    return cache["dialogues"]


# ============================================================
# API совместимый с vocabulary.py (использует текущий уровень)
# ============================================================

def get_all_words(major: str = None, sub: str = None) -> list:
    """Получить все слова как плоский список."""
    vocabulary = _load_all_vocabulary(major, sub)
    all_words = []
    
    level_key = _get_level_key(major, sub)
    
    for category_id, category in vocabulary.items():
        for word in category.get("words", []):
            all_words.append({
                "de": word.get("de", ""),
                "ru": word.get("ru", ""),
                "example": word.get("example", ""),
                "example_ru": word.get("example_ru", ""),
                "category_id": category_id,
                "category_name": category.get("name", ""),
                "word_id": f"{level_key}_{category_id}_{word.get('de', '')}",
                "level": level_key
            })
    
    return all_words


def get_words_by_category(category_id: str, major: str = None, sub: str = None) -> list:
    """Получить слова из определённой категории."""
    vocabulary = _load_all_vocabulary(major, sub)
    
    if category_id not in vocabulary:
        return []
    
    category = vocabulary[category_id]
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "de": word.get("de", ""),
            "ru": word.get("ru", ""),
            "example": word.get("example", ""),
            "example_ru": word.get("example_ru", ""),
            "category_id": category_id,
            "category_name": category.get("name", ""),
            "word_id": f"{level_key}_{category_id}_{word.get('de', '')}",
            "level": level_key
        }
        for word in category.get("words", [])
    ]


def get_category_distractors(category_id: str, major: str = None, sub: str = None) -> list:
    """Получить список distractors (отвлекающих слов) из категории."""
    vocabulary = _load_all_vocabulary(major, sub)
    
    if category_id not in vocabulary:
        return []
    
    category = vocabulary[category_id]
    return category.get("distractors", [])


def get_categories(major: str = None, sub: str = None) -> list:
    """Получить список всех категорий."""
    vocabulary = _load_all_vocabulary(major, sub)
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "id": cat_id,
            "name": cat.get("name", ""),
            "name_de": cat.get("name_de", ""),
            "description": cat.get("description", ""),
            "count": len(cat.get("words", [])),
            "level": level_key
        }
        for cat_id, cat in vocabulary.items()
    ]


# ============================================================
# API совместимый с grammar.py
# ============================================================

def get_all_tests(major: str = None, sub: str = None) -> list:
    """Получить список всех тестов."""
    grammar = _load_all_grammar(major, sub)
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "id": test_id,
            "name": test.get("name", ""),
            "name_de": test.get("name_de", ""),
            "description": test.get("description", ""),
            "questions_count": len(test.get("questions", [])),
            "level": level_key
        }
        for test_id, test in grammar.items()
    ]


def get_test(test_id: str, major: str = None, sub: str = None) -> Optional[dict]:
    """Получить тест по ID."""
    grammar = _load_all_grammar(major, sub)
    return grammar.get(test_id)


def get_test_questions(test_id: str, major: str = None, sub: str = None) -> list:
    """Получить вопросы теста."""
    test = get_test(test_id, major, sub)
    if not test:
        return []
    return test.get("questions", [])


def get_grammar_theory(test_id: str, major: str = None, sub: str = None) -> Optional[dict]:
    """Получить теорию для грамматической темы."""
    test = get_test(test_id, major, sub)
    if not test:
        return None
    return test.get("theory")


# ============================================================
# Статистика
# ============================================================

def get_vocabulary_stats(major: str = None, sub: str = None) -> dict:
    """Получить статистику по словарю."""
    vocabulary = _load_all_vocabulary(major, sub)
    total_words = sum(len(cat.get("words", [])) for cat in vocabulary.values())
    level_key = _get_level_key(major, sub)
    
    return {
        "level": level_key,
        "total_categories": len(vocabulary),
        "total_words": total_words,
        "categories": [
            {"id": cat_id, "name": cat.get("name", ""), "words": len(cat.get("words", []))}
            for cat_id, cat in vocabulary.items()
        ]
    }


def get_grammar_stats(major: str = None, sub: str = None) -> dict:
    """Получить статистику по грамматике."""
    grammar = _load_all_grammar(major, sub)
    total_questions = sum(len(test.get("questions", [])) for test in grammar.values())
    level_key = _get_level_key(major, sub)
    
    return {
        "level": level_key,
        "total_topics": len(grammar),
        "total_questions": total_questions,
        "topics": [
            {"id": test_id, "name": test.get("name", ""), "questions": len(test.get("questions", []))}
            for test_id, test in grammar.items()
        ]
    }


# ============================================================
# API для Phrases
# ============================================================

def get_phrases_categories(major: str = None, sub: str = None) -> list:
    """Получить список всех категорий phrases."""
    phrases = _load_all_phrases(major, sub)
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "id": cat_id,
            "name": cat.get("name", ""),
            "name_de": cat.get("name_de", ""),
            "description": cat.get("description", ""),
            "count": len(cat.get("phrases", [])),
            "level": level_key
        }
        for cat_id, cat in phrases.items()
    ]


def get_phrases_by_category(category_id: str, major: str = None, sub: str = None) -> list:
    """Получить phrases из определённой категории."""
    phrases = _load_all_phrases(major, sub)
    
    if category_id not in phrases:
        return []
    
    category = phrases[category_id]
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "de": phrase.get("de", ""),
            "ru": phrase.get("ru", ""),
            "context": phrase.get("context", ""),
            "example": phrase.get("example", ""),
            "example_ru": phrase.get("example_ru", ""),
            "category_id": category_id,
            "category_name": category.get("name", ""),
            "phrase_id": f"{level_key}_{category_id}_{phrase.get('de', '')}",
            "level": level_key
        }
        for phrase in category.get("phrases", [])
    ]


# ============================================================
# API для Dialogues
# ============================================================

def get_dialogue_topics(major: str = None, sub: str = None) -> list:
    """Получить список всех тем dialogues."""
    dialogues = _load_all_dialogues(major, sub)
    level_key = _get_level_key(major, sub)
    
    return [
        {
            "id": topic_id,
            "name": topic.get("name", ""),
            "name_de": topic.get("name_de", ""),
            "description": topic.get("description", ""),
            "dialogue_length": len(topic.get("dialogue", [])),
            "level": level_key
        }
        for topic_id, topic in dialogues.items()
    ]


def get_dialogue(topic_id: str, major: str = None, sub: str = None) -> Optional[dict]:
    """Получить диалог по теме."""
    dialogues = _load_all_dialogues(major, sub)
    return dialogues.get(topic_id)


def get_dialogue_exercises(topic_id: str, major: str = None, sub: str = None) -> list:
    """Получить упражнения для диалога."""
    dialogue = get_dialogue(topic_id, major, sub)
    if not dialogue:
        return []
    return dialogue.get("exercises", [])


# ============================================================
# Управление кэшем и инициализация
# ============================================================

def reload_content(major: str = None, sub: str = None):
    """Перезагрузить данные для уровня (очистить кэш)."""
    if major is None:
        # Очистить весь кэш
        global _cache
        _cache = {}
        logger.info("Весь кэш контента очищен")
    else:
        # Очистить только для конкретного уровня
        key = _get_level_key(major, sub)
        if key in _cache:
            del _cache[key]
            logger.info(f"Кэш контента для уровня {key} очищен")


def reload_all_content():
    """Перезагрузить все данные (очистить весь кэш)."""
    global _cache
    _cache = {}
    logger.info("Весь кэш контента очищен")


def init_content(major: str = None, sub: str = None):
    """Инициализировать загрузку контента при старте."""
    if major is not None:
        set_level(major, sub)
    
    level_str = get_current_level_str()
    logger.info(f"Инициализация контента для уровня {level_str}...")
    
    _load_all_vocabulary()
    _load_all_grammar()
    _load_all_phrases()
    _load_all_dialogues()
    
    vocab_stats = get_vocabulary_stats()
    grammar_stats = get_grammar_stats()
    phrases = _load_all_phrases()
    dialogues = _load_all_dialogues()
    
    logger.info(f"[{level_str}] Загружено: {vocab_stats['total_words']} слов в {vocab_stats['total_categories']} категориях")
    logger.info(f"[{level_str}] Загружено: {grammar_stats['total_questions']} вопросов в {grammar_stats['total_topics']} темах")
    logger.info(f"[{level_str}] Загружено: {len(phrases)} категорий phrases")
    logger.info(f"[{level_str}] Загружено: {len(dialogues)} диалогов")


def init_all_levels():
    """Инициализировать контент для всех уровней с данными."""
    logger.info("Инициализация контента для всех уровней...")
    
    levels_with_content = get_levels_with_content()
    for level in levels_with_content:
        major, sub = level["major"], level["sub"]
        logger.info(f"Загрузка уровня {major}.{sub}...")
        _load_all_vocabulary(major, sub)
        _load_all_grammar(major, sub)
        _load_all_phrases(major, sub)
        _load_all_dialogues(major, sub)
    
    logger.info(f"Загружено {len(levels_with_content)} уровней с контентом")
