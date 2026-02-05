"""
Content Manager - загрузка и управление учебными данными из JSON файлов.

Этот модуль обеспечивает:
- Загрузку словаря и грамматических тестов из JSON
- Кэширование данных для быстрого доступа
- Обратную совместимость с существующим API
"""

import json
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Путь к папке с данными
DATA_DIR = Path(__file__).parent.parent / "data" / "A1"

# Кэш для загруженных данных
_vocabulary_cache: dict = {}
_grammar_cache: dict = {}
_phrases_cache: dict = {}
_dialogues_cache: dict = {}
_metadata_cache: Optional[dict] = None


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


def get_metadata() -> dict:
    """Получить метаданные уровня A1."""
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = _load_json(DATA_DIR / "metadata.json")
    return _metadata_cache


def _load_all_vocabulary() -> dict:
    """Загрузить все категории словаря."""
    global _vocabulary_cache
    
    if _vocabulary_cache:
        return _vocabulary_cache
    
    vocab_dir = DATA_DIR / "vocabulary"
    if not vocab_dir.exists():
        logger.error(f"Папка словаря не найдена: {vocab_dir}")
        return {}
    
    for json_file in vocab_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                _vocabulary_cache[data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(_vocabulary_cache)} категорий словаря")
    return _vocabulary_cache


def _load_all_grammar() -> dict:
    """Загрузить все грамматические тесты."""
    global _grammar_cache
    
    if _grammar_cache:
        return _grammar_cache
    
    grammar_dir = DATA_DIR / "grammar"
    if not grammar_dir.exists():
        logger.error(f"Папка грамматики не найдена: {grammar_dir}")
        return {}
    
    for json_file in grammar_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                _grammar_cache[data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(_grammar_cache)} грамматических тем")
    return _grammar_cache


def _load_all_phrases() -> dict:
    """Загрузить все категории фраз."""
    global _phrases_cache
    
    if _phrases_cache:
        return _phrases_cache
    
    phrases_dir = DATA_DIR / "phrases"
    if not phrases_dir.exists():
        logger.error(f"Папка phrases не найдена: {phrases_dir}")
        return {}
    
    for json_file in phrases_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                _phrases_cache[data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(_phrases_cache)} категорий phrases")
    return _phrases_cache


def _load_all_dialogues() -> dict:
    """Загрузить все диалоги."""
    global _dialogues_cache
    
    if _dialogues_cache:
        return _dialogues_cache
    
    dialogues_dir = DATA_DIR / "dialogues"
    if not dialogues_dir.exists():
        logger.error(f"Папка dialogues не найдена: {dialogues_dir}")
        return {}
    
    for json_file in dialogues_dir.glob("*.json"):
        try:
            data = _load_json(json_file)
            if data and "id" in data:
                _dialogues_cache[data["id"]] = data
        except Exception as e:
            logger.error(f"Ошибка загрузки {json_file}: {e}")
    
    logger.info(f"Загружено {len(_dialogues_cache)} диалогов")
    return _dialogues_cache


# ============================================================
# API совместимый с vocabulary.py
# ============================================================

def get_all_words() -> list:
    """Получить все слова как плоский список (совместимость с vocabulary.py)."""
    vocabulary = _load_all_vocabulary()
    all_words = []
    
    for category_id, category in vocabulary.items():
        for word in category.get("words", []):
            all_words.append({
                "de": word.get("de", ""),
                "ru": word.get("ru", ""),
                "example": word.get("example", ""),
                "example_ru": word.get("example_ru", ""),
                "category_id": category_id,
                "category_name": category.get("name", ""),
                "word_id": f"{category_id}_{word.get('de', '')}"
            })
    
    return all_words


def get_words_by_category(category_id: str) -> list:
    """Получить слова из определённой категории (совместимость с vocabulary.py)."""
    vocabulary = _load_all_vocabulary()
    
    if category_id not in vocabulary:
        return []
    
    category = vocabulary[category_id]
    return [
        {
            "de": word.get("de", ""),
            "ru": word.get("ru", ""),
            "example": word.get("example", ""),
            "example_ru": word.get("example_ru", ""),
            "category_id": category_id,
            "category_name": category.get("name", ""),
            "word_id": f"{category_id}_{word.get('de', '')}"
        }
        for word in category.get("words", [])
    ]


def get_category_distractors(category_id: str) -> list:
    """Получить список distractors (отвлекающих слов) из категории."""
    vocabulary = _load_all_vocabulary()
    
    if category_id not in vocabulary:
        return []
    
    category = vocabulary[category_id]
    return category.get("distractors", [])


def get_categories() -> list:
    """Получить список всех категорий (совместимость с vocabulary.py)."""
    vocabulary = _load_all_vocabulary()
    return [
        {
            "id": cat_id,
            "name": cat.get("name", ""),
            "name_de": cat.get("name_de", ""),
            "description": cat.get("description", ""),
            "count": len(cat.get("words", []))
        }
        for cat_id, cat in vocabulary.items()
    ]


# ============================================================
# API совместимый с grammar.py
# ============================================================

def get_all_tests() -> list:
    """Получить список всех тестов (совместимость с grammar.py)."""
    grammar = _load_all_grammar()
    return [
        {
            "id": test_id,
            "name": test.get("name", ""),
            "name_de": test.get("name_de", ""),
            "description": test.get("description", ""),
            "questions_count": len(test.get("questions", []))
        }
        for test_id, test in grammar.items()
    ]


def get_test(test_id: str) -> Optional[dict]:
    """Получить тест по ID (совместимость с grammar.py)."""
    grammar = _load_all_grammar()
    return grammar.get(test_id)


def get_test_questions(test_id: str) -> list:
    """Получить вопросы теста (совместимость с grammar.py)."""
    test = get_test(test_id)
    if not test:
        return []
    return test.get("questions", [])


def get_grammar_theory(test_id: str) -> Optional[dict]:
    """Получить теорию для грамматической темы (новый метод)."""
    test = get_test(test_id)
    if not test:
        return None
    return test.get("theory")


# ============================================================
# Новые методы
# ============================================================

def get_vocabulary_stats() -> dict:
    """Получить статистику по словарю."""
    vocabulary = _load_all_vocabulary()
    total_words = sum(len(cat.get("words", [])) for cat in vocabulary.values())
    
    return {
        "total_categories": len(vocabulary),
        "total_words": total_words,
        "categories": [
            {"id": cat_id, "name": cat.get("name", ""), "words": len(cat.get("words", []))}
            for cat_id, cat in vocabulary.items()
        ]
    }


def get_grammar_stats() -> dict:
    """Получить статистику по грамматике."""
    grammar = _load_all_grammar()
    total_questions = sum(len(test.get("questions", [])) for test in grammar.values())
    
    return {
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

def get_phrases_categories() -> list:
    """Получить список всех категорий phrases."""
    phrases = _load_all_phrases()
    return [
        {
            "id": cat_id,
            "name": cat.get("name", ""),
            "name_de": cat.get("name_de", ""),
            "description": cat.get("description", ""),
            "count": len(cat.get("phrases", []))
        }
        for cat_id, cat in phrases.items()
    ]


def get_phrases_by_category(category_id: str) -> list:
    """Получить phrases из определённой категории."""
    phrases = _load_all_phrases()
    
    if category_id not in phrases:
        return []
    
    category = phrases[category_id]
    return [
        {
            "de": phrase.get("de", ""),
            "ru": phrase.get("ru", ""),
            "context": phrase.get("context", ""),
            "example": phrase.get("example", ""),
            "example_ru": phrase.get("example_ru", ""),
            "category_id": category_id,
            "category_name": category.get("name", ""),
            "phrase_id": f"{category_id}_{phrase.get('de', '')}"
        }
        for phrase in category.get("phrases", [])
    ]


# ============================================================
# API для Dialogues
# ============================================================

def get_dialogue_topics() -> list:
    """Получить список всех тем dialogues."""
    dialogues = _load_all_dialogues()
    return [
        {
            "id": topic_id,
            "name": topic.get("name", ""),
            "name_de": topic.get("name_de", ""),
            "description": topic.get("description", ""),
            "dialogue_length": len(topic.get("dialogue", []))
        }
        for topic_id, topic in dialogues.items()
    ]


def get_dialogue(topic_id: str) -> Optional[dict]:
    """Получить диалог по теме."""
    dialogues = _load_all_dialogues()
    return dialogues.get(topic_id)


def get_dialogue_exercises(topic_id: str) -> list:
    """Получить упражнения для диалога."""
    dialogue = get_dialogue(topic_id)
    if not dialogue:
        return []
    return dialogue.get("exercises", [])


def reload_content():
    """Перезагрузить все данные (очистить кэш)."""
    global _vocabulary_cache, _grammar_cache, _phrases_cache, _dialogues_cache, _metadata_cache
    _vocabulary_cache = {}
    _grammar_cache = {}
    _phrases_cache = {}
    _dialogues_cache = {}
    _metadata_cache = None
    logger.info("Кэш контента очищен")


def init_content():
    """Инициализировать загрузку контента при старте."""
    logger.info("Инициализация контента...")
    _load_all_vocabulary()
    _load_all_grammar()
    _load_all_phrases()
    _load_all_dialogues()
    
    vocab_stats = get_vocabulary_stats()
    grammar_stats = get_grammar_stats()
    phrases = _load_all_phrases()
    dialogues = _load_all_dialogues()
    
    logger.info(f"Загружено: {vocab_stats['total_words']} слов в {vocab_stats['total_categories']} категориях")
    logger.info(f"Загружено: {grammar_stats['total_questions']} вопросов в {grammar_stats['total_topics']} темах")
    logger.info(f"Загружено: {len(phrases)} категорий phrases")
    logger.info(f"Загружено: {len(dialogues)} диалогов")