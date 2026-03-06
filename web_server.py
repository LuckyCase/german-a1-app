"""
Web server for Telegram Web App + Bot Webhook
Combined server for Render free tier (single web service)
"""
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os
import asyncio
import logging

from bot.content_manager import (
    get_all_words, get_categories, get_words_by_category,
    get_all_tests, get_test_questions, init_content,
    get_phrases_categories, get_phrases_by_category, get_all_phrases_flat,
    get_dialogue_topics, get_dialogue, get_dialogue_exercises,
    get_category_distractors,
    get_available_levels, get_levels_with_content, set_level,
    get_current_level_str, get_current_level,
    get_culture_topics, get_culture_topic,
    get_exercise_sets, get_exercise_set, get_exercise_tasks
)
from bot.database import (
    get_user_stats, update_word_progress, save_grammar_result,
    update_daily_stats, init_db, save_phrase_progress, save_dialogue_progress,
    save_culture_progress, save_exercise_set_progress,
    get_or_create_user, save_feedback, get_user_feedback, get_feedback_count,
    get_priority_word_ids, get_priority_phrase_ids,
    get_detailed_user_progress,
    FEEDBACK_STATUS_LABELS, MAX_FEEDBACK_LENGTH
)
from bot.config import TELEGRAM_BOT_TOKEN, DATABASE_URL

# Telegram bot imports
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers.common import start

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global bot application instance
bot_application = None


async def _redirect_to_webapp(update: Update, context):
    """Направить пользователя в Web App при любой команде кроме /start."""
    await update.message.reply_text(
        "Все функции (прогресс, карточки, грамматика, напоминания, аудио) доступны в веб-приложении.\n\n"
        "Нажмите /start и выберите «🚀 Открыть приложение»."
    )


def create_bot_application():
    """Create and configure the bot application.
    В режиме Web App обрабатывается только /start; остальные команды ведут в приложение.
    """
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Только /start — всё остальное в Web App
    application.add_handler(CommandHandler("start", start))
    # Любая другая команда из чата — подсказка открыть Web App
    application.add_handler(MessageHandler(filters.COMMAND, _redirect_to_webapp))

    return application


async def init_bot():
    """Initialize bot application."""
    global bot_application
    if bot_application is None:
        # Initialize database
        await init_db()
        # Create bot application
        bot_application = create_bot_application()
        await bot_application.initialize()
        logger.info("Bot application initialized")
    return bot_application


# Initialize bot on startup (lazy initialization - will be done on first webhook)
def init_app():
    """Initialize application on startup."""
    # Initialize content from JSON files
    init_content()
    # Initialize database (create tables if needed) — required for web API endpoints
    try:
        asyncio.run(init_db())
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    # Don't initialize bot here - do it lazily on first webhook request
    # This avoids event loop conflicts with gunicorn workers
    logger.info("Application ready - bot will be initialized on first request")

# Modern responsive HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>German A1 - Lernen</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --primary-light: #818cf8;
            --success: #10b981;
            --success-light: #34d399;
            --error: #ef4444;
            --error-light: #f87171;
            --warning: #f59e0b;
            --bg-primary: var(--tg-theme-bg-color, #0f0f23);
            --bg-secondary: var(--tg-theme-secondary-bg-color, #1a1a2e);
            --bg-card: rgba(255, 255, 255, 0.03);
            --text-primary: var(--tg-theme-text-color, #ffffff);
            --text-secondary: var(--tg-theme-hint-color, #a0a0b0);
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 20px;
            --radius-xl: 28px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        
        html, body {
            height: 100%;
            overflow-x: hidden;
        }
        
        body {
            font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
            min-height: 100dvh;
        }
        
        /* Animated gradient background */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 40% 60%, rgba(59, 130, 246, 0.08) 0%, transparent 40%);
            pointer-events: none;
            z-index: -1;
        }
        
        .app {
            width: 100%;
            max-width: 100%;
            margin: 0 auto;
            padding: 16px;
            padding-bottom: 100px;
        }
        
        @media (min-width: 768px) {
            .app {
                max-width: 1200px;
                padding: 24px;
            }
        }
        
        /* Header */
        .header {
            text-align: center;
            padding: 24px 16px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.15) 100%);
            border-radius: var(--radius-xl);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .header.compact {
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        
        .header.compact h1 {
            font-size: 1.2rem;
            margin-bottom: 0;
        }
        
        .header.compact p {
            display: none;
        }
        
        .header.compact::before {
            font-size: 60px;
            right: -10px;
            top: -10px;
        }
        
        .header.hidden {
            display: none;
        }
        
        .header::before {
            content: '🇩🇪';
            position: absolute;
            font-size: 120px;
            opacity: 0.05;
            right: -20px;
            top: -20px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .header h1 {
            font-size: clamp(1.5rem, 5vw, 1.8rem);
            font-weight: 800;
            background: linear-gradient(135deg, #fff 0%, #c7d2fe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 4px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .header p {
            color: var(--text-secondary);
            font-size: 0.9rem;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        /* Main menu with tiles */
        .main-menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        
        @media (min-width: 768px) {
            .main-menu {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }
        }
        
        .menu-tile {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 24px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            min-height: 140px;
            justify-content: center;
            /* button reset */
            -webkit-appearance: none;
            appearance: none;
            font-family: inherit;
            color: var(--text-primary);
            width: 100%;
        }
        
        .menu-tile:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2);
            border-color: var(--primary);
        }
        
        .menu-tile:active {
            transform: translateY(-2px);
        }
        
        .menu-tile-icon {
            font-size: 3rem;
            line-height: 1;
        }
        
        .menu-tile-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .menu-tile-desc {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        /* Content sections */
        .section {
            display: none;
            animation: slideUp 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .section.active {
            display: block;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 20px;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
        }
        
        .card-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Buttons */
        .btn {
            width: 100%;
            padding: 16px 20px;
            border: none;
            border-radius: var(--radius-md);
            font-family: inherit;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        }
        
        .btn-primary:active {
            transform: scale(0.98);
            box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3);
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .btn-ghost {
            background: transparent;
            color: var(--primary-light);
            padding: 12px;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        /* Category/Test buttons */
        .category-btn {
            background: var(--tg-theme-secondary-bg-color, var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 16px;
            text-align: left;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        
        .category-btn:active {
            background: var(--primary);
            border-color: var(--primary);
            transform: scale(0.98);
            color: white;
        }
        
        .category-btn .name {
            font-weight: 700;
            font-size: 1rem;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        
        .category-btn .count {
            color: var(--text-primary);
            font-size: 0.85rem;
            background: var(--tg-theme-button-color, rgba(99, 102, 241, 0.3));
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 600;
        }
        
        /* Flashcard */
        .flashcard {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-xl);
            padding: 32px 24px;
            text-align: center;
            margin-bottom: 20px;
            position: relative;
            overflow: hidden;
        }
        
        .flashcard::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--primary-light));
        }
        
        .flashcard-word {
            font-size: clamp(1.8rem, 6vw, 2.5rem);
            font-weight: 800;
            margin-bottom: 8px;
            color: var(--tg-theme-text-color, white);
        }
        
        .flashcard-example {
            color: var(--tg-theme-hint-color, var(--text-secondary));
            font-size: 0.95rem;
            font-style: italic;
            margin-bottom: 16px;
        }
        
        .flashcard-progress {
            font-size: 0.8rem;
            color: var(--text-primary);
            background: rgba(99, 102, 241, 0.2);
            padding: 6px 12px;
            border-radius: 20px;
            display: inline-block;
            margin-bottom: 16px;
            font-weight: 600;
        }
        
        .audio-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 20px;
            background: var(--tg-theme-button-color, rgba(99, 102, 241, 0.2));
            border: 1px solid var(--border-color);
            border-radius: 30px;
            color: var(--tg-theme-button-text-color, var(--text-primary));
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .audio-btn:active {
            background: var(--primary);
            border-color: var(--primary);
        }
        
        /* Options */
        .options {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .option {
            width: 100%;
            padding: 16px 20px;
            background: var(--tg-theme-secondary-bg-color, var(--bg-secondary));
            border: 2px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--tg-theme-text-color, var(--text-primary));
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
        }
        
        .option:active {
            border-color: var(--primary);
            background: rgba(99, 102, 241, 0.1);
        }
        
        .option.correct {
            background: rgba(16, 185, 129, 0.2);
            border-color: var(--success);
            color: var(--success-light);
        }
        
        .option.wrong {
            background: rgba(239, 68, 68, 0.2);
            border-color: var(--error);
            color: var(--error-light);
        }
        
        /* Progress page */
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.08);
            border-radius: 6px;
            overflow: hidden;
        }
        .progress-bar.large { height: 12px; margin-top: 12px; }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--primary-light));
            border-radius: 6px;
            transition: width 0.5s ease;
        }
        .progress-fill.orange { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .progress-fill.green { background: linear-gradient(90deg, #22c55e, #4ade80); }

        .prog-section {
            background: var(--tg-theme-secondary-bg-color, var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            margin-bottom: 12px;
            overflow: hidden;
        }
        .prog-section-header {
            display: flex;
            align-items: center;
            padding: 16px;
            cursor: pointer;
            gap: 12px;
            -webkit-tap-highlight-color: transparent;
        }
        .prog-section-header:active { opacity: 0.7; }
        .prog-section-icon { font-size: 1.4rem; flex-shrink: 0; }
        .prog-section-info { flex: 1; min-width: 0; }
        .prog-section-title {
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        .prog-section-subtitle {
            font-size: 0.78rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            margin-top: 2px;
        }
        .prog-section-arrow {
            font-size: 0.8rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            transition: transform 0.2s;
            flex-shrink: 0;
        }
        .prog-section.open .prog-section-arrow { transform: rotate(90deg); }
        .prog-section-bar { padding: 0 16px 12px; }
        .prog-section-details {
            display: none;
            padding: 0 16px 16px;
            border-top: 1px solid var(--border-color);
        }
        .prog-section.open .prog-section-details { display: block; }

        .prog-cat {
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .prog-cat:last-child { border-bottom: none; }
        .prog-cat-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .prog-cat-name {
            font-size: 0.85rem;
            color: var(--tg-theme-text-color, var(--text-primary));
            font-weight: 500;
        }
        .prog-cat-count {
            font-size: 0.78rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            font-weight: 600;
        }
        .prog-cat-meta {
            display: flex;
            gap: 12px;
            margin-top: 5px;
            font-size: 0.72rem;
        }
        .prog-cat-meta span {
            color: var(--tg-theme-hint-color, var(--text-secondary));
        }
        .prog-cat-meta .errors { color: #f87171; }
        .prog-cat-meta .mastered { color: #4ade80; }

        .prog-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .prog-item:last-child { border-bottom: none; }
        .prog-item-status { font-size: 0.9rem; flex-shrink: 0; }
        .prog-item-name {
            flex: 1;
            font-size: 0.85rem;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        .prog-item-score {
            font-size: 0.78rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            font-weight: 600;
        }
        
        /* Loading & Error */
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--tg-theme-hint-color, var(--text-secondary));
        }
        
        .loading::after {
            content: '';
            display: block;
            width: 30px;
            height: 30px;
            margin: 16px auto 0;
            border: 3px solid var(--border-color);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .error-msg {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid var(--error);
            color: var(--error-light);
            padding: 16px;
            border-radius: var(--radius-md);
            text-align: center;
        }
        
        /* Question card */
        .question-card {
            background: var(--tg-theme-secondary-bg-color, var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 24px;
            margin-bottom: 20px;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        
        .question-number {
            font-size: 0.8rem;
            color: var(--text-primary);
            background: rgba(99, 102, 241, 0.2);
            padding: 6px 12px;
            border-radius: 20px;
            display: inline-block;
            font-weight: 700;
            margin-bottom: 12px;
        }
        
        .question-text {
            font-size: 1.1rem;
            font-weight: 600;
            line-height: 1.6;
        }
        
        /* Back button */
        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 0;
            background: none;
            border: none;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            font-family: inherit;
            font-size: 0.9rem;
            cursor: pointer;
            margin-bottom: 16px;
        }
        
        /* Responsive */
        @media (max-width: 360px) {
            .app { padding: 12px; }
            .header { padding: 20px 12px; }
            .flashcard { padding: 24px 16px; }
            .main-menu {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            .menu-tile {
                padding: 20px 16px;
                min-height: 120px;
            }
            .menu-tile-icon {
                font-size: 2.5rem;
            }
        }
        
        @media (min-width: 481px) {
            .app { padding: 20px; }
        }
        
        @media (min-width: 1024px) {
            .main-menu {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        
        /* Safe area for notched phones */
        @supports (padding-bottom: env(safe-area-inset-bottom)) {
            .app {
                padding-bottom: calc(100px + env(safe-area-inset-bottom));
            }
        }
        
        /* Hidden audio element */
        audio { display: none; }
    </style>
</head>
<body>
    <div class="app">
        <header class="header" id="main-header">
            <h1>German A1</h1>
            <p>Учи немецкий легко и эффективно</p>
        </header>
        
        <!-- Main Menu -->
        <div id="main-menu" class="main-menu">
            <button type="button" class="menu-tile" data-section="flashcards">
                <div class="menu-tile-icon">📚</div>
                <div class="menu-tile-title">Слова</div>
                <div class="menu-tile-desc">Изучайте слова</div>
            </button>
            <button type="button" class="menu-tile" data-section="grammar">
                <div class="menu-tile-icon">📝</div>
                <div class="menu-tile-title">Грамматика</div>
                <div class="menu-tile-desc">Тесты по грамматике</div>
            </button>
            <button type="button" class="menu-tile" data-section="phrases">
                <div class="menu-tile-icon">💬</div>
                <div class="menu-tile-title">Фразы</div>
                <div class="menu-tile-desc">Полезные фразы</div>
            </button>
            <button type="button" class="menu-tile" data-section="dialogues">
                <div class="menu-tile-icon">🗣️</div>
                <div class="menu-tile-title">Диалоги</div>
                <div class="menu-tile-desc">Практика диалогов</div>
            </button>
            <button type="button" class="menu-tile" data-section="culture">
                <div class="menu-tile-icon">🇩🇪</div>
                <div class="menu-tile-title">Культура</div>
                <div class="menu-tile-desc">Традиции и реалии</div>
            </button>
            <button type="button" class="menu-tile" data-section="exercises">
                <div class="menu-tile-icon">✏️</div>
                <div class="menu-tile-title">Упражнения</div>
                <div class="menu-tile-desc">Проверь себя</div>
            </button>
            <button type="button" class="menu-tile" data-section="progress">
                <div class="menu-tile-icon">📊</div>
                <div class="menu-tile-title">Прогресс</div>
                <div class="menu-tile-desc">Ваша статистика</div>
            </button>
            <button type="button" class="menu-tile" data-section="feedback" style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(251, 191, 36, 0.1) 100%);">
                <div class="menu-tile-icon">💬</div>
                <div class="menu-tile-title">Отзыв</div>
                <div class="menu-tile-desc">Предложения</div>
            </button>
        </div>
        
        <!-- Flashcards Section -->
        <section id="flashcards" class="section" style="display: none;">
            <div id="categories-view">
                <button type="button" class="back-btn" data-action="backToMainFromCategories">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите категорию</h2>
                    <div id="categories-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="flashcard-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToCategories">← Назад к категориям</button>
                
                <div class="flashcard">
                    <div class="flashcard-progress" id="word-progress">Слово 1 из 10</div>
                    <div class="flashcard-word" id="word-de">Wort</div>
                    <div class="flashcard-example" id="word-example">Beispiel</div>
                    <button type="button" class="audio-btn" id="audio-btn" data-action="playAudio">
                        🔊 Прослушать
                    </button>
                </div>
                
                <div class="options" id="word-options"></div>
                
                <button type="button" class="btn btn-primary" id="next-btn" style="display: none; margin-top: 16px;" data-action="nextWord">
                    Следующее слово →
                </button>
            </div>
        </section>
        
        <!-- Grammar Section -->
        <section id="grammar" class="section">
            <div id="tests-view">
                <button type="button" class="back-btn" data-action="backToMainFromTests">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите тест</h2>
                    <div id="tests-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="grammar-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToTests">← Назад к тестам</button>
                
                <div class="question-card">
                    <div class="question-number" id="question-number">Вопрос 1 из 10</div>
                    <div class="question-text" id="question-text">Вопрос...</div>
                </div>
                
                <div class="options" id="question-options"></div>
                
                <button type="button" class="btn btn-primary" id="next-question-btn" style="display: none; margin-top: 16px;" data-action="nextQuestion">
                    Следующий вопрос →
                </button>
            </div>
        </section>
        
        <!-- Phrases Section -->
        <section id="phrases" class="section">
            <div id="phrases-categories-view">
                <button type="button" class="back-btn" data-action="backToMainFromPhrasesCategories">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите категорию</h2>
                    <div id="phrases-categories-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="phrases-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToPhrasesCategories">← Назад</button>
                <div class="flashcard">
                    <div class="flashcard-progress" id="phrase-progress">Фраза 1 из 10</div>
                    <div class="flashcard-word" id="phrase-de">Phrase</div>
                    <div class="flashcard-example" id="phrase-context">Context</div>
                    <div class="flashcard-example" id="phrase-example" style="margin-top: 8px;"></div>
                    <button type="button" class="audio-btn" data-action="playPhraseAudio">🔊 Прослушать</button>
                </div>
                <div class="options" id="phrase-options"></div>
                <button type="button" class="btn btn-primary" id="next-phrase-btn" style="display: none; margin-top: 16px;" data-action="nextPhrase">
                    Следующая фраза →
                </button>
            </div>
        </section>
        
        <!-- Dialogues Section -->
        <section id="dialogues" class="section">
            <div id="dialogues-topics-view">
                <button type="button" class="back-btn" data-action="backToMainFromDialoguesTopics">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите диалог</h2>
                    <div id="dialogues-topics-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="dialogue-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToDialoguesTopics">← Назад</button>
                <div id="dialogue-content" class="card"></div>
                <button type="button" class="btn btn-primary" id="dialogue-exercise-btn" style="margin-top: 16px;" data-action="showDialogueExercise">
                    Упражнение →
                </button>
            </div>
            
            <div id="dialogue-exercise-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToDialogue">← Назад к диалогу</button>
                <div class="question-card">
                    <div class="question-number" id="exercise-number">Упражнение 1 из 3</div>
                    <div class="question-text" id="exercise-question"></div>
                </div>
                <div class="options" id="exercise-options"></div>
                <button type="button" class="btn btn-primary" id="next-exercise-btn" style="display: none; margin-top: 16px;" data-action="nextExercise">
                    Следующее упражнение →
                </button>
            </div>
        </section>
        
        <!-- Culture Section -->
        <section id="culture" class="section" style="display: none;">
            <div id="culture-topics-view">
                <button type="button" class="back-btn" data-action="backToMainFromCulture">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите тему</h2>
                    <div id="culture-topics-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            <div id="culture-topic-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToCultureTopics">← Назад</button>
                <div id="culture-content" class="card"></div>
                <div id="culture-quiz-block" style="display: none; margin-top: 16px;">
                    <h3 class="card-title" style="margin-top: 16px;">Мини-викторина</h3>
                    <div class="question-card">
                        <div class="question-number" id="culture-quiz-number">Вопрос 1</div>
                        <div class="question-text" id="culture-quiz-question"></div>
                    </div>
                    <div class="options" id="culture-quiz-options"></div>
                    <button type="button" class="btn btn-primary" id="culture-quiz-next" style="display: none; margin-top: 16px;" data-action="nextCultureQuizQuestion">
                        Далее →
                    </button>
                </div>
            </div>
        </section>
        
        <!-- Exercises Section -->
        <section id="exercises" class="section" style="display: none;">
            <div id="exercises-sets-view">
                <button type="button" class="back-btn" data-action="backToMainFromExercises">← Назад в меню</button>
                <div class="card">
                    <h2 class="card-title">Выберите набор</h2>
                    <div id="exercises-sets-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            <div id="exercises-task-view" style="display: none;">
                <button type="button" class="back-btn" data-action="backToExercisesSets">← Назад</button>
                <div class="question-card">
                    <div class="question-number" id="ex-task-number">Задание 1 из 5</div>
                    <div class="question-text" id="ex-task-question"></div>
                </div>
                <div class="options" id="ex-task-options"></div>
                <div id="ex-task-explanation" style="display: none; margin-top: 16px; padding: 16px; background: var(--bg-secondary); border-radius: var(--radius-md); border-left: 4px solid var(--primary); color: var(--text-primary);"></div>
                <button type="button" class="btn btn-primary" id="ex-task-next" style="display: none; margin-top: 16px;" data-action="nextExTask">
                    Далее →
                </button>
            </div>
        </section>
        
        <!-- Progress Section -->
        <section id="progress" class="section" style="display: none;">
            <button type="button" class="back-btn" data-action="backToMainMenu">← Назад в меню</button>
            <div id="progress-content">
                <div class="loading">Загрузка...</div>
            </div>
        </section>
        
        <!-- Feedback Section -->
        <section id="feedback" class="section" style="display: none;">
            <button type="button" class="back-btn" data-action="backToMainMenu">← Назад в меню</button>
            
            <div class="card">
                <h2 class="card-title">💬 Отзыв / Предложение</h2>
                <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.9rem;">
                    Напишите нам! Мы ценим вашу обратную связь и постараемся учесть ваши пожелания.
                </p>
                
                <div id="feedback-form">
                    <textarea 
                        id="feedback-text" 
                        placeholder="Напишите ваш отзыв или предложение..."
                        maxlength="1000"
                        style="
                            width: 100%;
                            min-height: 120px;
                            padding: 16px;
                            border: 1px solid var(--border-color);
                            border-radius: var(--radius-md);
                            background: var(--bg-secondary);
                            color: var(--text-primary);
                            font-family: inherit;
                            font-size: 1rem;
                            resize: vertical;
                            margin-bottom: 8px;
                        "
                    ></textarea>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <span id="feedback-char-count" style="font-size: 0.85rem; color: var(--text-secondary);">0 / 1000</span>
                        <button type="button" class="btn btn-primary" data-action="submitFeedback" style="width: auto; padding: 12px 24px;">
                            ✉️ Отправить
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="card" id="feedback-history-card">
                <h2 class="card-title">📋 Ваши обращения</h2>
                <div id="feedback-list">
                    <div class="loading">Загрузка...</div>
                </div>
            </div>
        </section>
    </div>
    
    <audio id="word-audio"></audio>
    
    <script>
        const tg = window.Telegram?.WebApp || {};
        if (tg.ready) tg.ready();
        if (tg.expand) tg.expand();
        
        // Клики по тайлам главного меню
        document.getElementById('main-menu').addEventListener('click', function(e) {
            const tile = e.target.closest('.menu-tile');
            if (tile && tile.dataset.section) {
                openSection(tile.dataset.section);
            }
        });
        document.querySelector('.app').addEventListener('click', function(e) {
            const btn = e.target.closest('[data-action]');
            if (!btn || btn.tagName !== 'BUTTON') return;
            const action = btn.getAttribute('data-action');
            if (action && typeof window[action] === 'function') {
                e.preventDefault();
                window[action]();
            }
        });
        
        // Apply Telegram theme
        const theme = tg.themeParams || {};
        document.documentElement.style.setProperty('--bg-primary', theme.bg_color || '#0f0f23');
        document.documentElement.style.setProperty('--bg-secondary', theme.secondary_bg_color || '#1a1a2e');
        document.documentElement.style.setProperty('--text-primary', theme.text_color || '#ffffff');
        document.documentElement.style.setProperty('--text-secondary', theme.hint_color || '#a0a0b0');
        
        const userId = tg.initDataUnsafe?.user?.id;
        
        let currentCategory = null;
        let currentWords = [];
        let currentWordIndex = 0;
        let currentTest = null;
        let currentQuestions = [];
        let currentQuestionIndex = 0;
        let userScore = 0;
        let currentPhrasesCategory = null;
        let currentPhrases = [];
        let currentPhraseIndex = 0;
        let currentDialogueId = null;
        let currentDialogue = null;
        let currentDialogueReplicaIndex = 0;
        let currentExercises = [];
        let currentExerciseIndex = 0;
        let exerciseScore = 0;
        let currentCultureTopicData = null;
        let currentCultureQuestions = [];
        let currentCultureQuizIndex = 0;
        let currentCultureQuizCorrectCount = 0;
        let cultureQuizProgressSaved = false;
        let currentLevelMajor = 'A1';
        let currentLevelSub = '1';
        let currentExerciseSetId = null;
        let currentExTasks = [];
        let currentExTaskIndex = 0;
        let currentExScore = 0;
        
        // Header scroll behavior
        let headerShown = true;
        let scrollTimeout = null;
        
        function handleScroll() {
            const header = document.getElementById('main-header');
            // Only handle scroll if header is visible (not hidden)
            if (header.classList.contains('hidden')) {
                return;
            }
            
            const scrollY = window.scrollY || document.documentElement.scrollTop;
            
            if (scrollY > 50 && headerShown) {
                header.classList.add('compact');
                headerShown = false;
            } else if (scrollY <= 50 && !headerShown) {
                header.classList.remove('compact');
                headerShown = true;
            }
        }
        
        // Throttle scroll events
        window.addEventListener('scroll', () => {
            if (scrollTimeout) {
                clearTimeout(scrollTimeout);
            }
            scrollTimeout = setTimeout(handleScroll, 10);
        });
        
        // Show full header on page load, then allow compact mode
        let initialLoad = true;
        setTimeout(() => {
            initialLoad = false;
            handleScroll();
        }, 2000);
        
        // Section navigation
        function openSection(sectionId) {
            document.getElementById('main-menu').style.display = 'none';
            document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
            document.getElementById(sectionId).style.display = 'block';
            
            // Hide header when entering sections
            const header = document.getElementById('main-header');
            header.classList.add('hidden');
            header.classList.remove('compact');
            
            // Load data for specific sections
            if (sectionId === 'flashcards') {
                loadCategories();
            } else if (sectionId === 'grammar') {
                loadTests();
            } else if (sectionId === 'phrases') {
                loadPhrasesCategories();
            } else if (sectionId === 'dialogues') {
                loadDialoguesTopics();
            } else if (sectionId === 'culture') {
                loadCultureTopics();
            } else if (sectionId === 'exercises') {
                loadExercisesSets();
            } else if (sectionId === 'progress') {
                loadProgress();
            } else if (sectionId === 'feedback') {
                loadFeedback();
            }
            
            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
            
            tg.HapticFeedback?.selectionChanged();
        }
        
        function backToMainMenu() {
            document.getElementById('main-menu').style.display = 'grid';
            document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
            
            // Show header when returning to main menu
            const header = document.getElementById('main-header');
            header.classList.remove('hidden', 'compact');
            headerShown = true;
            
            // Reset views
            document.getElementById('categories-view').style.display = 'block';
            document.getElementById('flashcard-view').style.display = 'none';
            document.getElementById('tests-view').style.display = 'block';
            document.getElementById('grammar-view').style.display = 'none';
            document.getElementById('phrases-categories-view').style.display = 'block';
            document.getElementById('phrases-view').style.display = 'none';
            document.getElementById('dialogues-topics-view').style.display = 'block';
            document.getElementById('dialogue-view').style.display = 'none';
            document.getElementById('dialogue-exercise-view').style.display = 'none';
            document.getElementById('culture-topics-view').style.display = 'block';
            document.getElementById('culture-topic-view').style.display = 'none';
            document.getElementById('exercises-sets-view').style.display = 'block';
            document.getElementById('exercises-task-view').style.display = 'none';
            
            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        
        // Categories
        async function loadCategories() {
            try {
                const response = await fetch('/api/categories');
                const categories = await response.json();
                const list = document.getElementById('categories-list');
                list.innerHTML = '';
                
                categories.forEach(cat => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `
                        <span class="name">${cat.name}</span>
                        <span class="count">${cat.count} слов</span>
                    `;
                    btn.onclick = () => startFlashcards(cat.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('categories-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки категорий</div>';
            }
        }
        
        async function startFlashcards(categoryId) {
            try {
                const response = await fetch(`/api/session/words?category=${categoryId}&user_id=${userId}`);
                currentWords = await response.json();
                currentWordIndex = 0;
                currentCategory = categoryId;
                wordSessionCorrect = 0;
                wordSessionWrong = 0;
                
                document.getElementById('categories-view').style.display = 'none';
                document.getElementById('flashcard-view').style.display = 'block';
                
                showNextWord();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки слов');
            }
        }
        
        function backToCategories() {
            document.getElementById('flashcard-view').style.display = 'none';
            document.getElementById('categories-view').style.display = 'block';
        }
        
        function backToMainFromCategories() {
            backToMainMenu();
        }
        
        async function showNextWord() {
            if (currentWordIndex >= currentWords.length) {
                // Show results screen
                const total = wordSessionCorrect + wordSessionWrong;
                const pct = total > 0 ? Math.round(wordSessionCorrect / total * 100) : 0;
                document.getElementById('word-progress').textContent = 'Упражнение завершено!';
                document.getElementById('word-de').textContent = `${pct}%`;
                document.getElementById('word-example').textContent =
                    `Правильно: ${wordSessionCorrect} из ${total}`;
                document.getElementById('word-options').innerHTML = '';
                document.getElementById('next-btn').style.display = 'none';
                document.getElementById('audio-btn').style.display = 'none';

                const finishBtn = document.createElement('button');
                finishBtn.className = 'btn btn-primary';
                finishBtn.style.marginTop = '16px';
                finishBtn.textContent = '← Назад к категориям';
                finishBtn.onclick = () => {
                    document.getElementById('audio-btn').style.display = '';
                    backToCategories();
                };
                document.getElementById('word-options').appendChild(finishBtn);

                tg.HapticFeedback?.notificationOccurred('success');
                return;
            }
            
            const word = currentWords[currentWordIndex];
            document.getElementById('word-progress').textContent = 
                `Слово ${currentWordIndex + 1} из ${currentWords.length}`;
            document.getElementById('word-de').textContent = word.de;
            document.getElementById('word-example').textContent = word.example || '';
            
            // Reset audio
            const audio = document.getElementById('word-audio');
            const audioBtn = document.getElementById('audio-btn');
            audio.pause();
            audio.onerror = null;
            audio.onloadeddata = null;
            audio.src = '';
            audioBtn.textContent = '🔊 Прослушать';
            audioBtn.disabled = false;
            
            // Get options from the same category
            const response = await fetch(`/api/words/random?count=3&exclude=${word.word_id}&exclude_ru=${encodeURIComponent(word.ru)}&category=${currentCategory}`);
            const wrongWords = await response.json();
            const options = [word, ...wrongWords].sort(() => Math.random() - 0.5);
            
            const optionsDiv = document.getElementById('word-options');
            optionsDiv.innerHTML = '';
            
            options.forEach((opt, index) => {
                const btn = document.createElement('button');
                btn.className = 'option';
                btn.textContent = opt.ru;
                btn.onclick = () => selectAnswer(btn, opt.word_id === word.word_id, word.ru);
                optionsDiv.appendChild(btn);
            });
            
            document.getElementById('next-btn').style.display = 'none';
        }
        
        async function playAudio() {
            const word = currentWords[currentWordIndex];
            if (!word) return;
            
            const audio = document.getElementById('word-audio');
            const audioBtn = document.getElementById('audio-btn');
            
            if (audio.src && audio.src.includes(encodeURIComponent(word.de))) {
                audio.currentTime = 0;
                audio.play().catch(() => tg.showAlert?.('Ошибка воспроизведения'));
                return;
            }
            
            audioBtn.textContent = '⏳ Загрузка...';
            audioBtn.disabled = true;
            
            try {
                audio.src = `/api/audio/${encodeURIComponent(word.de)}`;
                
                audio.onloadeddata = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    audio.play().catch(() => {
                        tg.showAlert?.('Ошибка воспроизведения');
                        audioBtn.textContent = '🔊 Прослушать';
                    });
                };
                
                audio.onerror = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    tg.showAlert?.('Ошибка загрузки аудио');
                };
                
                audio.load();
            } catch (error) {
                audioBtn.textContent = '🔊 Прослушать';
                audioBtn.disabled = false;
            }
        }
        
        let wordSessionCorrect = 0;
        let wordSessionWrong = 0;

        async function selectAnswer(selectedBtn, isCorrect, correctAnswer) {
            const buttons = document.querySelectorAll('#word-options .option');
            buttons.forEach(btn => {
                btn.onclick = null;
                if (btn === selectedBtn) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (btn.textContent === correctAnswer && !isCorrect) {
                    btn.classList.add('correct');
                }
            });

            if (isCorrect) wordSessionCorrect++; else wordSessionWrong++;

            const word = currentWords[currentWordIndex];
            fetch('/api/progress/word', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    word_id: word.word_id,
                    is_correct: isCorrect
                })
            });

            tg.HapticFeedback?.notificationOccurred(isCorrect ? 'success' : 'error');

            const nextBtn = document.getElementById('next-btn');
            if (currentWordIndex + 1 >= currentWords.length) {
                nextBtn.textContent = 'Завершить ✓';
            } else {
                nextBtn.textContent = 'Следующее слово →';
            }
            nextBtn.style.display = 'block';
        }

        function nextWord() {
            currentWordIndex++;
            showNextWord();
        }
        
        // Grammar tests
        async function loadTests() {
            try {
                const response = await fetch('/api/tests');
                const tests = await response.json();
                const list = document.getElementById('tests-list');
                list.innerHTML = '';
                
                tests.forEach(test => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `
                        <span class="name">${test.name}</span>
                        <span class="count">${test.questions_count} вопросов</span>
                    `;
                    btn.onclick = () => startTest(test.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('tests-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки тестов</div>';
            }
        }
        
        async function startTest(testId) {
            try {
                const response = await fetch(`/api/tests/${testId}/questions`);
                currentQuestions = await response.json();
                currentQuestionIndex = 0;
                currentTest = testId;
                userScore = 0;
                
                document.getElementById('tests-view').style.display = 'none';
                document.getElementById('grammar-view').style.display = 'block';
                
                showNextQuestion();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки теста');
            }
        }
        
        function backToTests() {
            document.getElementById('grammar-view').style.display = 'none';
            document.getElementById('tests-view').style.display = 'block';
        }
        
        function backToMainFromTests() {
            backToMainMenu();
        }
        
        function showNextQuestion() {
            if (currentQuestionIndex >= currentQuestions.length) {
                finishTest();
                return;
            }
            
            const question = currentQuestions[currentQuestionIndex];
            document.getElementById('question-number').textContent = 
                `Вопрос ${currentQuestionIndex + 1} из ${currentQuestions.length}`;
            document.getElementById('question-text').textContent = question.question;
            
            const optionsDiv = document.getElementById('question-options');
            optionsDiv.innerHTML = '';
            
            question.options.forEach((option, index) => {
                const btn = document.createElement('button');
                btn.className = 'option';
                btn.textContent = option;
                btn.onclick = () => selectGrammarAnswer(btn, index === question.correct, question.options[question.correct]);
                optionsDiv.appendChild(btn);
            });
            
            document.getElementById('next-question-btn').style.display = 'none';
        }
        
        async function selectGrammarAnswer(selectedBtn, isCorrect, correctAnswer) {
            const buttons = document.querySelectorAll('#question-options .option');
            buttons.forEach(btn => {
                btn.onclick = null;
                if (btn === selectedBtn) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (btn.textContent === correctAnswer && !isCorrect) {
                    btn.classList.add('correct');
                }
            });
            
            if (isCorrect) userScore++;
            tg.HapticFeedback?.notificationOccurred(isCorrect ? 'success' : 'error');
            document.getElementById('next-question-btn').style.display = 'block';
        }
        
        function nextQuestion() {
            currentQuestionIndex++;
            showNextQuestion();
        }
        
        async function finishTest() {
            const total = currentQuestions.length;
            const percentage = Math.round((userScore / total) * 100);
            
            fetch('/api/progress/grammar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    test_id: currentTest,
                    score: userScore,
                    total: total
                })
            });
            
            tg.showAlert?.(`🎉 Тест завершён!\\nРезультат: ${userScore} из ${total} (${percentage}%)`);
            backToTests();
        }
        
        // Progress
        function toggleProgSection(el) {
            el.closest('.prog-section').classList.toggle('open');
            tg.HapticFeedback?.selectionChanged();
        }

        function pct(a, b) { return b > 0 ? Math.round(a / b * 100) : 0; }

        function renderCategoryDetails(categories) {
            return categories.map(c => {
                const notStarted = c.total - c.learned;
                return `<div class="prog-cat">
                    <div class="prog-cat-header">
                        <span class="prog-cat-name">${c.name}</span>
                        <span class="prog-cat-count">${c.learned} / ${c.total}</span>
                    </div>
                    <div class="progress-bar"><div class="progress-fill" style="width:${pct(c.learned, c.total)}%"></div></div>
                    <div class="prog-cat-meta">
                        <span class="mastered">${c.mastered} освоено</span>
                        ${c.errors > 0 ? `<span class="errors">${c.errors} ошиб.</span>` : ''}
                        ${notStarted > 0 ? `<span>${notStarted} не изуч.</span>` : ''}
                    </div>
                </div>`;
            }).join('');
        }

        function renderItemDetails(items, type) {
            return items.map(item => {
                let status, score;
                if (type === 'grammar') {
                    status = item.completed ? '&#10004;' : '&#9711;';
                    score = item.completed ? `${item.score}/${item.total} (${pct(item.score, item.total)}%)` : 'не пройден';
                } else if (type === 'culture') {
                    status = item.viewed ? '&#10004;' : '&#9711;';
                    score = item.viewed ? (item.quiz_total > 0 ? `Квиз: ${item.quiz_correct}/${item.quiz_total}` : 'просмотрено') : 'не просмотрено';
                } else {
                    status = item.completed ? '&#10004;' : '&#9711;';
                    score = item.completed ? `${item.correct}/${item.total}` : 'не пройден';
                }
                return `<div class="prog-item">
                    <span class="prog-item-status" style="color:${item.completed || item.viewed ? '#4ade80' : '#6b7280'}">${status}</span>
                    <span class="prog-item-name">${item.name}</span>
                    <span class="prog-item-score">${score}</span>
                </div>`;
            }).join('');
        }

        async function loadProgress() {
            const container = document.getElementById('progress-content');
            try {
                if (!userId) {
                    container.innerHTML = '<div class="error-msg">Не удалось определить пользователя. Откройте приложение через Telegram.</div>';
                    return;
                }
                const response = await fetch(`/api/progress?user_id=${userId}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const d = await response.json();

                const sections = [
                    {
                        icon: '&#128218;', title: 'Слова',
                        sub: `${d.words.learned} изучено / ${d.words.total} всего`,
                        pct: pct(d.words.learned, d.words.total),
                        details: renderCategoryDetails(d.words.categories)
                    },
                    {
                        icon: '&#128172;', title: 'Фразы',
                        sub: `${d.phrases.learned} изучено / ${d.phrases.total} всего`,
                        pct: pct(d.phrases.learned, d.phrases.total),
                        details: renderCategoryDetails(d.phrases.categories)
                    },
                    {
                        icon: '&#128221;', title: 'Грамматика',
                        sub: `${d.grammar.completed} из ${d.grammar.total} тестов пройдено`,
                        pct: pct(d.grammar.completed, d.grammar.total),
                        details: renderItemDetails(d.grammar.tests, 'grammar')
                    },
                    {
                        icon: '&#128483;', title: 'Диалоги',
                        sub: `${d.dialogues.completed} из ${d.dialogues.total} пройдено`,
                        pct: pct(d.dialogues.completed, d.dialogues.total),
                        details: renderItemDetails(d.dialogues.items, 'dialogues')
                    },
                    {
                        icon: '&#127963;', title: 'Культура',
                        sub: `${d.culture.viewed} из ${d.culture.total} просмотрено`,
                        pct: pct(d.culture.viewed, d.culture.total),
                        details: renderItemDetails(d.culture.items, 'culture')
                    },
                    {
                        icon: '&#9999;', title: 'Упражнения',
                        sub: `${d.exercises.completed} из ${d.exercises.total} выполнено`,
                        pct: pct(d.exercises.completed, d.exercises.total),
                        details: renderItemDetails(d.exercises.items, 'exercises')
                    }
                ];

                container.innerHTML = sections.map(s => `
                    <div class="prog-section">
                        <div class="prog-section-header" onclick="toggleProgSection(this)">
                            <span class="prog-section-icon">${s.icon}</span>
                            <div class="prog-section-info">
                                <div class="prog-section-title">${s.title}</div>
                                <div class="prog-section-subtitle">${s.sub}</div>
                            </div>
                            <span class="prog-section-arrow">&#9656;</span>
                        </div>
                        <div class="prog-section-bar">
                            <div class="progress-bar"><div class="progress-fill" style="width:${s.pct}%"></div></div>
                        </div>
                        <div class="prog-section-details">${s.details || '<div style="padding:8px 0;color:var(--text-secondary);font-size:0.85rem;">Нет данных</div>'}</div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('loadProgress error:', error);
                container.innerHTML = '<div class="error-msg">Ошибка загрузки статистики. Попробуйте позже.</div>';
            }
        }
        
        // Phrases functions
        async function loadPhrasesCategories() {
            try {
                const response = await fetch('/api/phrases/categories');
                const categories = await response.json();
                const list = document.getElementById('phrases-categories-list');
                list.innerHTML = '';
                
                categories.forEach(cat => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `
                        <span class="name">${cat.name}</span>
                        <span class="count">${cat.count} фраз</span>
                    `;
                    btn.onclick = () => startPhrases(cat.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('phrases-categories-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки категорий</div>';
            }
        }
        
        let phraseSessionCorrect = 0;
        let phraseSessionWrong = 0;

        async function startPhrases(categoryId) {
            try {
                const response = await fetch(`/api/session/phrases?category=${categoryId}&user_id=${userId}`);
                currentPhrases = await response.json();
                currentPhraseIndex = 0;
                currentPhrasesCategory = categoryId;
                phraseSessionCorrect = 0;
                phraseSessionWrong = 0;
                
                document.getElementById('phrases-categories-view').style.display = 'none';
                document.getElementById('phrases-view').style.display = 'block';
                
                showNextPhrase();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки фраз');
            }
        }
        
        function backToPhrasesCategories() {
            document.getElementById('phrases-view').style.display = 'none';
            document.getElementById('phrases-categories-view').style.display = 'block';
        }
        
        function backToMainFromPhrasesCategories() {
            backToMainMenu();
        }
        
        async function showNextPhrase() {
            if (currentPhraseIndex >= currentPhrases.length) {
                // Show results screen
                const total = phraseSessionCorrect + phraseSessionWrong;
                const pct = total > 0 ? Math.round(phraseSessionCorrect / total * 100) : 0;
                document.getElementById('phrase-progress').textContent = 'Упражнение завершено!';
                document.getElementById('phrase-de').textContent = `${pct}%`;
                document.getElementById('phrase-context').textContent =
                    `Правильно: ${phraseSessionCorrect} из ${total}`;
                document.getElementById('phrase-example').textContent = '';
                document.getElementById('phrase-options').innerHTML = '';
                document.getElementById('next-phrase-btn').style.display = 'none';
                const phraseAudioBtn = document.querySelector('#phrases-view .audio-btn');
                if (phraseAudioBtn) phraseAudioBtn.style.display = 'none';

                const finishBtn = document.createElement('button');
                finishBtn.className = 'btn btn-primary';
                finishBtn.style.marginTop = '16px';
                finishBtn.textContent = '← Назад к категориям';
                finishBtn.onclick = () => {
                    if (phraseAudioBtn) phraseAudioBtn.style.display = '';
                    backToPhrasesCategories();
                };
                document.getElementById('phrase-options').appendChild(finishBtn);

                tg.HapticFeedback?.notificationOccurred('success');
                return;
            }
            
            const phrase = currentPhrases[currentPhraseIndex];
            document.getElementById('phrase-progress').textContent = 
                `Фраза ${currentPhraseIndex + 1} из ${currentPhrases.length}`;
            document.getElementById('phrase-de').textContent = phrase.de;
            document.getElementById('phrase-context').textContent = phrase.context || '';
            document.getElementById('phrase-example').textContent = phrase.example || '';
            
            // Reset audio
            const audio = document.getElementById('word-audio');
            const audioBtn = document.querySelector('#phrases-view .audio-btn');
            audio.pause();
            audio.onerror = null;
            audio.onloadeddata = null;
            audio.src = '';
            if (audioBtn) {
                audioBtn.textContent = '🔊 Прослушать';
                audioBtn.disabled = false;
            }
            
            // Get wrong options
            const optResponse = await fetch(`/api/phrases/random?count=3&exclude=${phrase.phrase_id}&exclude_ru=${encodeURIComponent(phrase.ru)}`);
            const wrongPhrases = await optResponse.json();
            const options = [phrase, ...wrongPhrases].sort(() => Math.random() - 0.5);

            const optionsDiv = document.getElementById('phrase-options');
            optionsDiv.innerHTML = '';

            options.forEach((opt) => {
                const btn = document.createElement('button');
                btn.className = 'option';
                btn.textContent = opt.ru;
                btn.onclick = () => selectPhraseAnswer(btn, opt.phrase_id === phrase.phrase_id, phrase.ru);
                optionsDiv.appendChild(btn);
            });
            
            document.getElementById('next-phrase-btn').style.display = 'none';
        }
        
        async function playPhraseAudio() {
            const phrase = currentPhrases[currentPhraseIndex];
            if (!phrase) return;
            
            const audio = document.getElementById('word-audio');
            const audioBtn = document.querySelector('#phrases-view .audio-btn');
            
            if (audio.src && audio.src.includes(encodeURIComponent(phrase.de))) {
                audio.currentTime = 0;
                audio.play().catch(() => tg.showAlert?.('Ошибка воспроизведения'));
                return;
            }
            
            audioBtn.textContent = '⏳ Загрузка...';
            audioBtn.disabled = true;
            
            try {
                audio.src = `/api/audio/${encodeURIComponent(phrase.de)}`;
                
                audio.onloadeddata = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    audio.play().catch(() => {
                        tg.showAlert?.('Ошибка воспроизведения');
                        audioBtn.textContent = '🔊 Прослушать';
                    });
                };
                
                audio.onerror = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    tg.showAlert?.('Ошибка загрузки аудио');
                };
                
                audio.load();
            } catch (error) {
                audioBtn.textContent = '🔊 Прослушать';
                audioBtn.disabled = false;
            }
        }
        
        async function selectPhraseAnswer(selectedBtn, isCorrect, correctAnswer) {
            const buttons = document.querySelectorAll('#phrase-options .option');
            buttons.forEach(btn => {
                btn.onclick = null;
                if (btn === selectedBtn) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (btn.textContent === correctAnswer && !isCorrect) {
                    btn.classList.add('correct');
                }
            });

            if (isCorrect) phraseSessionCorrect++; else phraseSessionWrong++;

            const phrase = currentPhrases[currentPhraseIndex];
            fetch('/api/progress/phrase', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    phrase_id: phrase.phrase_id,
                    category_id: phrase.category_id,
                    is_correct: isCorrect
                })
            });

            tg.HapticFeedback?.notificationOccurred(isCorrect ? 'success' : 'error');

            const nextPhrBtn = document.getElementById('next-phrase-btn');
            if (currentPhraseIndex + 1 >= currentPhrases.length) {
                nextPhrBtn.textContent = 'Завершить ✓';
            } else {
                nextPhrBtn.textContent = 'Следующая фраза →';
            }
            nextPhrBtn.style.display = 'block';
        }
        
        function nextPhrase() {
            currentPhraseIndex++;
            showNextPhrase();
        }
        
        // Dialogues functions
        async function loadDialoguesTopics() {
            try {
                const response = await fetch('/api/dialogues/topics');
                const topics = await response.json();
                const list = document.getElementById('dialogues-topics-list');
                list.innerHTML = '';
                
                topics.forEach(topic => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `
                        <span class="name">${topic.name}</span>
                        <span class="count">${topic.dialogue_length} реплик</span>
                    `;
                    btn.onclick = () => startDialogue(topic.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('dialogues-topics-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки диалогов</div>';
            }
        }
        
        async function startDialogue(topicId) {
            try {
                const response = await fetch(`/api/dialogues/${topicId}`);
                currentDialogue = await response.json();
                currentDialogueId = topicId;
                currentDialogueReplicaIndex = 0;
                
                document.getElementById('dialogues-topics-view').style.display = 'none';
                document.getElementById('dialogue-view').style.display = 'block';
                
                showDialogue();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки диалога');
            }
        }
        
        function backToDialoguesTopics() {
            document.getElementById('dialogue-view').style.display = 'none';
            document.getElementById('dialogue-exercise-view').style.display = 'none';
            document.getElementById('dialogues-topics-view').style.display = 'block';
        }
        
        function backToMainFromDialoguesTopics() {
            backToMainMenu();
        }
        
        function backToDialogue() {
            document.getElementById('dialogue-exercise-view').style.display = 'none';
            document.getElementById('dialogue-view').style.display = 'block';
        }
        
        function showDialogue() {
            if (!currentDialogue || !currentDialogue.dialogue) return;
            
            const contentDiv = document.getElementById('dialogue-content');
            contentDiv.innerHTML = `<h2 style="margin-bottom: 16px; color: var(--text-primary);">${currentDialogue.name}</h2>`;
            
            currentDialogue.dialogue.forEach((replica, index) => {
                const replicaDiv = document.createElement('div');
                replicaDiv.style.cssText = 'margin-bottom: 16px; padding: 12px; background: var(--bg-secondary); border-radius: var(--radius-md); border-left: 3px solid var(--primary);';
                replicaDiv.innerHTML = `
                    <div style="font-weight: 700; color: var(--primary-light); margin-bottom: 4px;">
                        ${replica.role} ${replica.role_ru ? `(${replica.role_ru})` : ''}
                    </div>
                    <div style="font-size: 1.1rem; margin-bottom: 4px; color: var(--text-primary);">
                        ${replica.text}
                    </div>
                    <div style="font-size: 0.9rem; color: var(--text-secondary); font-style: italic;">
                        ${replica.text_ru}
                    </div>
                `;
                contentDiv.appendChild(replicaDiv);
            });
        }
        
        async function showDialogueExercise() {
            try {
                const response = await fetch(`/api/dialogues/${currentDialogueId}/exercises`);
                currentExercises = await response.json();
                currentExerciseIndex = 0;
                exerciseScore = 0;
                
                if (currentExercises.length === 0) {
                    tg.showAlert?.('Упражнения для этого диалога пока не готовы');
                    return;
                }
                
                document.getElementById('dialogue-view').style.display = 'none';
                document.getElementById('dialogue-exercise-view').style.display = 'block';
                
                showNextExercise();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки упражнений');
            }
        }
        
        function showNextExercise() {
            if (currentExerciseIndex >= currentExercises.length) {
                finishDialogueExercise();
                return;
            }
            
            const exercise = currentExercises[currentExerciseIndex];
            document.getElementById('exercise-number').textContent = 
                `Упражнение ${currentExerciseIndex + 1} из ${currentExercises.length}`;
            document.getElementById('exercise-question').textContent = exercise.question;
            
            const optionsDiv = document.getElementById('exercise-options');
            optionsDiv.innerHTML = '';
            
            exercise.options.forEach((option, index) => {
                const btn = document.createElement('button');
                btn.className = 'option';
                btn.textContent = option;
                btn.onclick = () => selectExerciseAnswer(btn, index === exercise.correct, exercise.options[exercise.correct]);
                optionsDiv.appendChild(btn);
            });
            
            document.getElementById('next-exercise-btn').style.display = 'none';
        }
        
        async function selectExerciseAnswer(selectedBtn, isCorrect, correctAnswer) {
            const buttons = document.querySelectorAll('#exercise-options .option');
            buttons.forEach(btn => {
                btn.onclick = null;
                if (btn === selectedBtn) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (btn.textContent === correctAnswer && !isCorrect) {
                    btn.classList.add('correct');
                }
            });
            
            if (isCorrect) exerciseScore++;
            tg.HapticFeedback?.notificationOccurred(isCorrect ? 'success' : 'error');
            document.getElementById('next-exercise-btn').style.display = 'block';
        }
        
        function nextExercise() {
            currentExerciseIndex++;
            showNextExercise();
        }
        
        async function finishDialogueExercise() {
            const total = currentExercises.length;
            const percentage = Math.round((exerciseScore / total) * 100);
            
            fetch('/api/progress/dialogue', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    dialogue_id: currentDialogueId,
                    exercises_completed: total,
                    exercises_correct: exerciseScore
                })
            });
            
            tg.showAlert?.(`🎉 Упражнение завершено!\\nРезультат: ${exerciseScore} из ${total} (${percentage}%)`);
            backToDialogue();
        }
        
        // ============= CULTURE FUNCTIONS =============
        
        async function loadCultureTopics() {
            try {
                const levelRes = await fetch('/api/levels/current');
                if (levelRes.ok) {
                    const levelData = await levelRes.json();
                    currentLevelMajor = levelData.major || 'A1';
                    currentLevelSub = levelData.sub || '1';
                }
                const response = await fetch('/api/culture/topics');
                const topics = await response.json();
                const list = document.getElementById('culture-topics-list');
                list.innerHTML = '';
                if (topics.length === 0) {
                    list.innerHTML = '<p style="color: var(--text-secondary);">Тем пока нет</p>';
                    return;
                }
                topics.forEach(topic => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `<span class="name">${topic.name}</span>`;
                    btn.onclick = () => openCultureTopic(topic.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('culture-topics-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки тем</div>';
            }
        }
        
        async function openCultureTopic(topicId) {
            try {
                const response = await fetch(`/api/culture/${topicId}`);
                currentCultureTopicData = await response.json();
                currentCultureQuestions = currentCultureTopicData.questions || [];
                currentCultureQuizIndex = 0;
                currentCultureQuizCorrectCount = 0;
                cultureQuizProgressSaved = false;
                
                document.getElementById('culture-topics-view').style.display = 'none';
                document.getElementById('culture-topic-view').style.display = 'block';
                
                renderCultureContent();
                const quizBlock = document.getElementById('culture-quiz-block');
                if (currentCultureQuestions.length > 0) {
                    quizBlock.style.display = 'block';
                    showCultureQuizQuestion();
                } else {
                    quizBlock.style.display = 'none';
                }
                if (userId) {
                    fetch('/api/progress/culture', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            user_id: userId,
                            topic_id: topicId,
                            major: currentLevelMajor,
                            sub: currentLevelSub
                        })
                    }).catch(() => {});
                }
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки темы');
            }
        }
        
        function renderCultureContent() {
            const content = currentCultureTopicData.content || {};
            const div = document.getElementById('culture-content');
            let html = `<h2 style="margin-bottom: 16px; color: var(--text-primary);">${currentCultureTopicData.name}</h2>`;
            if (content.title) html += `<h3 style="font-size: 1.1rem; color: var(--primary-light); margin-bottom: 12px;">${content.title}</h3>`;
            if (content.text) html += `<p style="color: var(--text-primary); line-height: 1.6; margin-bottom: 16px;">${content.text.replace(/\\n/g, '<br>')}</p>`;
            if (content.facts && content.facts.length) {
                html += '<p class="card-title" style="margin-top: 16px;">Факты</p><ul style="margin-left: 20px; color: var(--text-primary); margin-bottom: 16px;">';
                content.facts.forEach(f => { html += `<li>${f}</li>`; });
                html += '</ul>';
            }
            if (content.tips && content.tips.length) {
                html += '<p class="card-title">Советы</p><ul style="margin-left: 20px; color: var(--text-primary);">';
                content.tips.forEach(t => { html += `<li>${t}</li>`; });
                html += '</ul>';
            }
            div.innerHTML = html;
        }
        
        function showCultureQuizQuestion() {
            const optionsDiv = document.getElementById('culture-quiz-options');
            const nextBtn = document.getElementById('culture-quiz-next');
            const quizTotal = Math.min(2, currentCultureQuestions.length);
            if (currentCultureQuizIndex >= quizTotal) {
                if (userId && !cultureQuizProgressSaved && quizTotal > 0) {
                    cultureQuizProgressSaved = true;
                    fetch('/api/progress/culture', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            user_id: userId,
                            topic_id: currentCultureTopicData.id,
                            major: currentLevelMajor,
                            sub: currentLevelSub,
                            quiz_completed: 1,
                            quiz_correct: currentCultureQuizCorrectCount,
                            quiz_total: quizTotal
                        })
                    }).catch(() => {});
                }
                document.getElementById('culture-quiz-number').textContent = '';
                document.getElementById('culture-quiz-question').textContent = 'Викторина завершена';
                optionsDiv.innerHTML = '';
                nextBtn.style.display = 'none';
                return;
            }
            const q = currentCultureQuestions[currentCultureQuizIndex];
            document.getElementById('culture-quiz-number').textContent = `Вопрос ${currentCultureQuizIndex + 1}`;
            document.getElementById('culture-quiz-question').textContent = q.question;
            optionsDiv.innerHTML = '';
            nextBtn.style.display = 'none';
            nextBtn.onclick = () => { currentCultureQuizIndex++; showCultureQuizQuestion(); };
            q.options.forEach((opt, idx) => {
                const btn = document.createElement('button');
                btn.className = 'option';
                btn.textContent = opt;
                btn.onclick = () => {
                    optionsDiv.querySelectorAll('.option').forEach(b => { b.onclick = null; });
                    if (idx === q.correct) currentCultureQuizCorrectCount++;
                    btn.classList.add(idx === q.correct ? 'correct' : 'wrong');
                    if (idx !== q.correct) {
                        const correctBtn = optionsDiv.children[q.correct];
                        if (correctBtn) correctBtn.classList.add('correct');
                    }
                    tg.HapticFeedback?.notificationOccurred(idx === q.correct ? 'success' : 'error');
                    nextBtn.style.display = 'block';
                };
                optionsDiv.appendChild(btn);
            });
        }
        
        function nextCultureQuizQuestion() {
            currentCultureQuizIndex++;
            showCultureQuizQuestion();
        }
        
        function backToCultureTopics() {
            document.getElementById('culture-topic-view').style.display = 'none';
            document.getElementById('culture-topics-view').style.display = 'block';
        }
        
        function backToMainFromCulture() {
            backToMainMenu();
        }
        
        // ============= EXERCISES (STANDALONE) FUNCTIONS =============
        
        async function loadExercisesSets() {
            try {
                const levelRes = await fetch('/api/levels/current');
                if (levelRes.ok) {
                    const levelData = await levelRes.json();
                    currentLevelMajor = levelData.major || 'A1';
                    currentLevelSub = levelData.sub || '1';
                }
                const response = await fetch('/api/exercises/sets');
                const sets = await response.json();
                const list = document.getElementById('exercises-sets-list');
                list.innerHTML = '';
                if (sets.length === 0) {
                    list.innerHTML = '<p style="color: var(--text-secondary);">Наборов пока нет</p>';
                    return;
                }
                sets.forEach(s => {
                    const btn = document.createElement('button');
                    btn.className = 'category-btn';
                    btn.innerHTML = `
                        <span class="name">${s.name}</span>
                        <span class="count">${s.tasks_count} заданий</span>
                    `;
                    btn.onclick = () => startExerciseSet(s.id);
                    list.appendChild(btn);
                });
            } catch (error) {
                document.getElementById('exercises-sets-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки наборов</div>';
            }
        }
        
        async function startExerciseSet(setId) {
            try {
                const response = await fetch(`/api/exercises/${setId}/tasks`);
                currentExTasks = await response.json();
                currentExTaskIndex = 0;
                currentExScore = 0;
                currentExerciseSetId = setId;
                
                document.getElementById('exercises-sets-view').style.display = 'none';
                document.getElementById('exercises-task-view').style.display = 'block';
                
                showExTask();
            } catch (error) {
                tg.showAlert?.('Ошибка загрузки заданий');
            }
        }
        
        function showExTask() {
            if (currentExTaskIndex >= currentExTasks.length) {
                finishExSet();
                return;
            }
            const task = currentExTasks[currentExTaskIndex];
            document.getElementById('ex-task-number').textContent = `Задание ${currentExTaskIndex + 1} из ${currentExTasks.length}`;
            document.getElementById('ex-task-question').textContent = task.question;
            document.getElementById('ex-task-explanation').style.display = 'none';
            document.getElementById('ex-task-explanation').textContent = '';
            document.getElementById('ex-task-next').style.display = 'none';
            
            const optionsDiv = document.getElementById('ex-task-options');
            optionsDiv.innerHTML = '';
            if (task.options) {
                task.options.forEach((opt, idx) => {
                    const btn = document.createElement('button');
                    btn.className = 'option';
                    btn.textContent = opt;
                    btn.onclick = () => selectExTaskAnswer(btn, idx === task.correct, task.explanation);
                    optionsDiv.appendChild(btn);
                });
            }
        }
        
        function selectExTaskAnswer(selectedBtn, isCorrect, explanation) {
            const optionsDiv = document.getElementById('ex-task-options');
            optionsDiv.querySelectorAll('.option').forEach(btn => {
                btn.onclick = null;
                if (btn === selectedBtn) btn.classList.add(isCorrect ? 'correct' : 'wrong');
            });
            const correctIndex = currentExTasks[currentExTaskIndex].correct;
            if (!isCorrect && optionsDiv.children[correctIndex]) {
                optionsDiv.children[correctIndex].classList.add('correct');
            }
            if (isCorrect) currentExScore++;
            tg.HapticFeedback?.notificationOccurred(isCorrect ? 'success' : 'error');
            const explEl = document.getElementById('ex-task-explanation');
            if (explanation) {
                explEl.textContent = explanation;
                explEl.style.display = 'block';
            }
            document.getElementById('ex-task-next').style.display = 'block';
        }
        
        function nextExTask() {
            currentExTaskIndex++;
            showExTask();
        }
        
        function finishExSet() {
            const total = currentExTasks.length;
            const percentage = Math.round((currentExScore / total) * 100);
            if (userId && currentExerciseSetId) {
                fetch('/api/progress/exercise', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: userId,
                        set_id: currentExerciseSetId,
                        major: currentLevelMajor,
                        sub: currentLevelSub,
                        tasks_completed: total,
                        tasks_correct: currentExScore
                    })
                }).catch(() => {});
            }
            tg.showAlert?.(`🎉 Набор завершён!\\nРезультат: ${currentExScore} из ${total} (${percentage}%)`);
            backToExercisesSets();
        }
        
        function backToExercisesSets() {
            document.getElementById('exercises-task-view').style.display = 'none';
            document.getElementById('exercises-sets-view').style.display = 'block';
        }
        
        function backToMainFromExercises() {
            backToMainMenu();
        }
        
        // ============= FEEDBACK FUNCTIONS =============
        
        const FEEDBACK_STATUS_LABELS = {
            0: "📝 Отправлено",
            1: "👀 Просмотрено",
            2: "✅ Принято",
            3: "🔧 В работе",
            4: "🎉 Готово!",
            5: "❌ Отклонено"
        };
        
        // Character counter for feedback textarea
        document.addEventListener('DOMContentLoaded', () => {
            const textarea = document.getElementById('feedback-text');
            const counter = document.getElementById('feedback-char-count');
            
            if (textarea && counter) {
                textarea.addEventListener('input', () => {
                    const len = textarea.value.length;
                    counter.textContent = `${len} / 1000`;
                    counter.style.color = len > 900 ? 'var(--error)' : 'var(--text-secondary)';
                });
            }
        });
        
        async function loadFeedback() {
            if (!userId) {
                document.getElementById('feedback-list').innerHTML = 
                    '<div class="error-msg">Необходима авторизация через Telegram</div>';
                return;
            }
            
            try {
                const response = await fetch(`/api/feedback?user_id=${userId}`);
                const data = await response.json();
                
                const list = document.getElementById('feedback-list');
                
                if (!data.feedback || data.feedback.length === 0) {
                    list.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 20px;">У вас пока нет обращений</p>';
                    document.getElementById('feedback-history-card').style.display = 'none';
                    return;
                }
                
                document.getElementById('feedback-history-card').style.display = 'block';
                list.innerHTML = '';
                
                data.feedback.forEach(fb => {
                    const statusLabel = FEEDBACK_STATUS_LABELS[fb.status] || `Статус ${fb.status}`;
                    const date = new Date(fb.created_at).toLocaleDateString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    
                    const item = document.createElement('div');
                    item.style.cssText = `
                        background: var(--bg-secondary);
                        border: 1px solid var(--border-color);
                        border-radius: var(--radius-md);
                        padding: 16px;
                        margin-bottom: 12px;
                    `;
                    
                    // Truncate text if too long
                    const displayText = fb.text.length > 150 ? fb.text.substring(0, 150) + '...' : fb.text;
                    
                    item.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <span style="font-size: 0.85rem; color: var(--text-secondary);">#${fb.id} • ${date}</span>
                            <span style="font-size: 0.85rem; background: rgba(99, 102, 241, 0.2); padding: 4px 10px; border-radius: 12px;">${statusLabel}</span>
                        </div>
                        <p style="color: var(--text-primary); line-height: 1.5; word-wrap: break-word;">${displayText}</p>
                    `;
                    list.appendChild(item);
                });
                
                if (data.total > data.feedback.length) {
                    const moreText = document.createElement('p');
                    moreText.style.cssText = 'text-align: center; color: var(--text-secondary); font-size: 0.85rem; margin-top: 12px;';
                    moreText.textContent = `Показаны последние ${data.feedback.length} из ${data.total}`;
                    list.appendChild(moreText);
                }
                
            } catch (error) {
                document.getElementById('feedback-list').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки обращений</div>';
            }
        }
        
        async function submitFeedback() {
            if (!userId) {
                tg.showAlert?.('Необходима авторизация через Telegram');
                return;
            }
            
            const textarea = document.getElementById('feedback-text');
            const text = textarea.value.trim();
            
            if (!text) {
                tg.showAlert?.('Пожалуйста, введите текст отзыва');
                return;
            }
            
            if (text.length > 1000) {
                tg.showAlert?.('Текст слишком длинный. Максимум 1000 символов.');
                return;
            }
            
            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: userId,
                        text: text
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    tg.showAlert?.(`✅ Спасибо за ваш отзыв!\\n\\nНомер обращения: #${result.feedback_id}`);
                    tg.HapticFeedback?.notificationOccurred('success');
                    textarea.value = '';
                    document.getElementById('feedback-char-count').textContent = '0 / 1000';
                    loadFeedback(); // Reload list
                } else {
                    tg.showAlert?.('Ошибка отправки: ' + (result.error || 'Неизвестная ошибка'));
                    tg.HapticFeedback?.notificationOccurred('error');
                }
            } catch (error) {
                tg.showAlert?.('Ошибка отправки отзыва');
                tg.HapticFeedback?.notificationOccurred('error');
            }
        }
        
        // Initialize
        window.onload = () => {
            loadCategories();
            loadTests();
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/levels')
def api_levels():
    """Get all available levels with their content status."""
    levels = get_available_levels()
    return jsonify(levels)


@app.route('/api/levels/with-content')
def api_levels_with_content():
    """Get only levels that have content."""
    levels = get_levels_with_content()
    return jsonify(levels)


@app.route('/api/levels/current')
def api_current_level():
    """Get current level."""
    major, sub = get_current_level()
    return jsonify({
        "major": major,
        "sub": sub,
        "name": f"{major}.{sub}"
    })


@app.route('/api/levels/set', methods=['POST'])
def api_set_level():
    """Set current level."""
    data = request.json
    major = data.get('major', 'A1')
    sub = data.get('sub', '1')
    
    success = set_level(major, sub)
    
    if success:
        return jsonify({
            "success": True,
            "level": f"{major}.{sub}"
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Invalid level: {major}.{sub}"
        }), 400


@app.route('/api/categories')
def api_categories():
    """Get categories for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    if major and sub:
        categories = get_categories(major, sub)
    else:
        categories = get_categories()
    
    return jsonify(categories)

@app.route('/api/words')
def api_words():
    """Get words for current level or specified level."""
    category_id = request.args.get('category')
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    if category_id and category_id != 'all':
        words = get_words_by_category(category_id, major, sub) if major and sub else get_words_by_category(category_id)
    else:
        words = get_all_words(major, sub) if major and sub else get_all_words()
    
    return jsonify(words)

SESSION_SIZE = 10
MAX_ERROR_WORDS = 5
MAX_ERROR_PHRASES = 5


@app.route('/api/session/words')
def api_session_words():
    """Build a session of up to SESSION_SIZE words with error priority."""
    import random

    category_id = request.args.get('category')
    user_id = request.args.get('user_id', type=int)
    major = request.args.get('major')
    sub = request.args.get('sub')

    if category_id and category_id != 'all':
        words = get_words_by_category(category_id, major, sub) if major and sub else get_words_by_category(category_id)
    else:
        words = get_all_words(major, sub) if major and sub else get_all_words()

    if not words:
        return jsonify([])

    # Build session with error priority (same logic as bot handler)
    word_ids = [w["word_id"] for w in words]
    error_ids = []
    if user_id:
        try:
            error_ids = asyncio.run(get_priority_word_ids(user_id, word_ids))
        except Exception:
            pass

    word_map = {w["word_id"]: w for w in words}
    error_words = [word_map[wid] for wid in error_ids[:MAX_ERROR_WORDS] if wid in word_map]
    error_id_set = set(wid for wid in error_ids[:MAX_ERROR_WORDS])
    remaining = [w for w in words if w["word_id"] not in error_id_set]
    random.shuffle(remaining)
    fill_count = SESSION_SIZE - len(error_words)
    new_words = remaining[:fill_count]

    session = error_words + new_words
    random.shuffle(session)
    return jsonify(session)


@app.route('/api/session/phrases')
def api_session_phrases():
    """Build a session of up to SESSION_SIZE phrases with error priority."""
    import random

    category_id = request.args.get('category')
    user_id = request.args.get('user_id', type=int)
    major = request.args.get('major')
    sub = request.args.get('sub')

    if category_id:
        phrases = get_phrases_by_category(category_id, major, sub) if major and sub else get_phrases_by_category(category_id)
    else:
        phrases = get_all_phrases_flat(major, sub) if major and sub else get_all_phrases_flat()

    if not phrases:
        return jsonify([])

    # Deduplicate
    seen = set()
    unique = []
    for p in phrases:
        if p["phrase_id"] not in seen:
            seen.add(p["phrase_id"])
            unique.append(p)

    # Build session with error priority
    phrase_ids = [p["phrase_id"] for p in unique]
    error_ids = []
    if user_id:
        try:
            error_ids = asyncio.run(get_priority_phrase_ids(user_id, phrase_ids))
        except Exception:
            pass

    phrase_map = {p["phrase_id"]: p for p in unique}
    error_phrases = [phrase_map[pid] for pid in error_ids[:MAX_ERROR_PHRASES] if pid in phrase_map]
    error_id_set = set(pid for pid in error_ids[:MAX_ERROR_PHRASES])
    remaining = [p for p in unique if p["phrase_id"] not in error_id_set]
    random.shuffle(remaining)
    fill_count = SESSION_SIZE - len(error_phrases)
    new_phrases = remaining[:fill_count]

    session = error_phrases + new_phrases
    random.shuffle(session)
    return jsonify(session)


@app.route('/api/words/random')
def api_random_words():
    """Get random words for current level or specified level."""
    count = int(request.args.get('count', 3))
    exclude = request.args.get('exclude', '')
    exclude_ru = request.args.get('exclude_ru', '')
    category = request.args.get('category', '')
    major = request.args.get('major')
    sub = request.args.get('sub')

    import random

    # If category specified, get words from that category only
    if category:
        words = get_words_by_category(category, major, sub) if major and sub else get_words_by_category(category)
    else:
        words = get_all_words(major, sub) if major and sub else get_all_words()

    filtered = [w for w in words
                if w.get('word_id') != exclude and w.get('ru') != exclude_ru]
    
    # If not enough words in category, use distractors first
    if len(filtered) < count and category:
        distractors = get_category_distractors(category, major, sub) if major and sub else get_category_distractors(category)
        if distractors:
            # Create fake word objects from distractors
            needed = count - len(filtered)
            selected_distractors = random.sample(distractors, min(needed, len(distractors)))
            for d in selected_distractors:
                filtered.append({
                    "de": "",
                    "ru": d,
                    "word_id": f"distractor_{d}",
                    "category_id": category
                })
    
    # If still not enough, supplement from all words
    if len(filtered) < count:
        all_words = get_all_words(major, sub) if major and sub else get_all_words()
        extra = [w for w in all_words if w.get('word_id') != exclude and w not in filtered]
        filtered.extend(extra)
    
    return jsonify(random.sample(filtered, min(count, len(filtered))))

@app.route('/api/tests')
def api_tests():
    """Get tests for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    tests = get_all_tests(major, sub) if major and sub else get_all_tests()
    return jsonify(tests)


@app.route('/api/tests/<test_id>/questions')
def api_test_questions(test_id):
    """Get test questions for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    questions = get_test_questions(test_id, major, sub) if major and sub else get_test_questions(test_id)
    return jsonify(questions)

@app.route('/api/progress')
def api_progress():
    """Detailed progress with per-category breakdown for all content types."""
    user_id = request.args.get('user_id', type=int)

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        raw = asyncio.run(get_detailed_user_progress(user_id))
    except Exception as e:
        logger.error(f"Error getting detailed progress for {user_id}: {e}")
        raw = {'words': [], 'phrases': [], 'grammar': [], 'dialogues': [], 'culture': [], 'exercises': []}

    # --- Words ---
    all_words = get_all_words()
    word_progress_map = {wp['word_id']: wp for wp in raw['words']}

    word_cats = {}
    for w in all_words:
        cid = w['category_id']
        if cid not in word_cats:
            word_cats[cid] = {'id': cid, 'name': w['category_name'], 'total': 0, 'learned': 0, 'errors': 0, 'mastered': 0}
        word_cats[cid]['total'] += 1
        if w['word_id'] in word_progress_map:
            wp = word_progress_map[w['word_id']]
            word_cats[cid]['learned'] += 1
            if wp['wrong_count'] > 0:
                word_cats[cid]['errors'] += 1
            if wp['correct_count'] >= 3 and wp['wrong_count'] == 0:
                word_cats[cid]['mastered'] += 1

    # --- Phrases ---
    all_phrases = get_all_phrases_flat()
    phrase_progress_map = {pp['phrase_id']: pp for pp in raw['phrases']}

    phrase_cats = {}
    for p in all_phrases:
        cid = p.get('category_id', 'unknown')
        if cid not in phrase_cats:
            phrase_cats[cid] = {'id': cid, 'name': p.get('category_name', cid), 'total': 0, 'learned': 0, 'errors': 0, 'mastered': 0}
        phrase_cats[cid]['total'] += 1
        pid = p.get('phrase_id')
        if pid and pid in phrase_progress_map:
            pp = phrase_progress_map[pid]
            phrase_cats[cid]['learned'] += 1
            if pp['wrong_count'] > 0:
                phrase_cats[cid]['errors'] += 1
            if pp['correct_count'] >= 3 and pp['wrong_count'] == 0:
                phrase_cats[cid]['mastered'] += 1

    # --- Grammar ---
    all_tests = get_all_tests()
    grammar_best = {}
    for gr in raw['grammar']:
        tid = gr['test_id']
        if tid not in grammar_best or gr['score'] > grammar_best[tid]['score']:
            grammar_best[tid] = gr

    grammar_items = []
    for test in all_tests:
        tid = test['id']
        if tid in grammar_best:
            g = grammar_best[tid]
            grammar_items.append({'id': tid, 'name': test.get('name', tid), 'completed': True, 'score': g['score'], 'total': g['total']})
        else:
            grammar_items.append({'id': tid, 'name': test.get('name', tid), 'completed': False, 'score': 0, 'total': test.get('questions_count', 0)})

    # --- Dialogues ---
    dialogue_topics = get_dialogue_topics()
    dialogue_map = {d['dialogue_id']: d for d in raw['dialogues']}

    dialogue_items = []
    for topic in dialogue_topics:
        did = topic.get('id', '')
        if did in dialogue_map:
            d = dialogue_map[did]
            dialogue_items.append({'id': did, 'name': topic.get('name', did), 'completed': True, 'correct': d['exercises_correct'], 'total': d['exercises_completed']})
        else:
            dialogue_items.append({'id': did, 'name': topic.get('name', did), 'completed': False, 'correct': 0, 'total': 0})

    # --- Culture ---
    culture_topics_list = get_culture_topics()
    culture_map = {c['topic_id']: c for c in raw['culture']}

    culture_items = []
    for topic in culture_topics_list:
        tid = topic.get('id', '')
        if tid in culture_map:
            c = culture_map[tid]
            culture_items.append({'id': tid, 'name': topic.get('name', tid), 'viewed': True, 'quiz_correct': c.get('quiz_correct', 0), 'quiz_total': c.get('quiz_total', 0)})
        else:
            culture_items.append({'id': tid, 'name': topic.get('name', tid), 'viewed': False, 'quiz_correct': 0, 'quiz_total': 0})

    # --- Exercises ---
    exercise_sets_list = get_exercise_sets()
    exercise_map = {e['set_id']: e for e in raw['exercises']}

    exercise_items = []
    for s in exercise_sets_list:
        sid = s.get('id', '')
        if sid in exercise_map:
            e = exercise_map[sid]
            exercise_items.append({'id': sid, 'name': s.get('name', sid), 'completed': True, 'correct': e['tasks_correct'], 'total': e['tasks_completed']})
        else:
            exercise_items.append({'id': sid, 'name': s.get('name', sid), 'completed': False, 'correct': 0, 'total': s.get('tasks_count', 0)})

    return jsonify({
        'words': {
            'total': sum(c['total'] for c in word_cats.values()),
            'learned': sum(c['learned'] for c in word_cats.values()),
            'mastered': sum(c['mastered'] for c in word_cats.values()),
            'errors': sum(c['errors'] for c in word_cats.values()),
            'categories': sorted(word_cats.values(), key=lambda x: x['name'])
        },
        'phrases': {
            'total': sum(c['total'] for c in phrase_cats.values()),
            'learned': sum(c['learned'] for c in phrase_cats.values()),
            'mastered': sum(c['mastered'] for c in phrase_cats.values()),
            'errors': sum(c['errors'] for c in phrase_cats.values()),
            'categories': sorted(phrase_cats.values(), key=lambda x: x['name'])
        },
        'grammar': {
            'total': len(all_tests),
            'completed': sum(1 for g in grammar_items if g['completed']),
            'tests': grammar_items
        },
        'dialogues': {
            'total': len(dialogue_topics),
            'completed': sum(1 for d in dialogue_items if d['completed']),
            'items': dialogue_items
        },
        'culture': {
            'total': len(culture_topics_list),
            'viewed': sum(1 for c in culture_items if c['viewed']),
            'items': culture_items
        },
        'exercises': {
            'total': len(exercise_sets_list),
            'completed': sum(1 for e in exercise_items if e['completed']),
            'items': exercise_items
        }
    })

@app.route('/api/progress/word', methods=['POST'])
def api_update_word_progress():
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        asyncio.run(get_or_create_user(user_id, None, None))

        is_correct = data.get('is_correct', False)
        asyncio.run(update_word_progress(user_id, data['word_id'], is_correct))

        words = 1 if is_correct else 0
        correct = 1 if is_correct else 0
        asyncio.run(update_daily_stats(user_id, words=words, correct=correct, total=1))

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving word progress for user {user_id}: {e}")
        return jsonify({'error': 'Failed to save progress'}), 500

@app.route('/api/progress/grammar', methods=['POST'])
def api_save_grammar_result():
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        asyncio.run(get_or_create_user(user_id, None, None))
        asyncio.run(save_grammar_result(user_id, data['test_id'], data['score'], data['total']))
        asyncio.run(update_daily_stats(user_id, tests=1, correct=data['score'], total=data['total']))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving grammar result for user {user_id}: {e}")
        return jsonify({'error': 'Failed to save result'}), 500

@app.route('/api/audio/<text>')
def api_audio(text):
    """Generate and return audio file for given text (on-the-fly, no caching)."""
    from flask import Response
    from gtts import gTTS
    from urllib.parse import unquote
    import io

    # Decode URL-encoded text
    text = unquote(text)

    try:
        # Generate audio directly to memory
        tts = gTTS(text=text, lang='de', slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return Response(
            audio_buffer.getvalue(),
            mimetype='audio/mpeg',
            headers={'Content-Disposition': 'inline'}
        )
    except Exception as e:
        return jsonify({'error': f'Failed to generate audio: {str(e)}'}), 500


# ============= PHRASES API ENDPOINTS =============

@app.route('/api/phrases/categories')
def api_phrases_categories():
    """Get all phrases categories for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    categories = get_phrases_categories(major, sub) if major and sub else get_phrases_categories()
    return jsonify(categories)


@app.route('/api/phrases')
def api_phrases():
    """Get phrases by category for current level or specified level."""
    category_id = request.args.get('category')
    major = request.args.get('major')
    sub = request.args.get('sub')

    if category_id:
        phrases = get_phrases_by_category(category_id, major, sub) if major and sub else get_phrases_by_category(category_id)
    else:
        phrases = []

    return jsonify(phrases)


@app.route('/api/phrases/random')
def api_random_phrases():
    """Get random phrases for wrong answer options."""
    import random

    count = int(request.args.get('count', 3))
    exclude = request.args.get('exclude', '')
    exclude_ru = request.args.get('exclude_ru', '')
    major = request.args.get('major')
    sub = request.args.get('sub')

    all_phrases = get_all_phrases_flat(major, sub) if major and sub else get_all_phrases_flat()
    filtered = [p for p in all_phrases
                if p.get('phrase_id') != exclude and p.get('ru') != exclude_ru]

    return jsonify(random.sample(filtered, min(count, len(filtered))))


# ============= DIALOGUES API ENDPOINTS =============

@app.route('/api/dialogues/topics')
def api_dialogue_topics():
    """Get all dialogue topics for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    topics = get_dialogue_topics(major, sub) if major and sub else get_dialogue_topics()
    return jsonify(topics)


@app.route('/api/dialogues/<topic_id>')
def api_dialogue(topic_id):
    """Get dialogue by topic ID for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')
    
    dialogue = get_dialogue(topic_id, major, sub) if major and sub else get_dialogue(topic_id)
    return jsonify(dialogue) if dialogue else jsonify({'error': 'Not found'}), 404


@app.route('/api/dialogues/<topic_id>/exercises')
def api_dialogue_exercises(topic_id):
    """Get exercises for dialogue for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    exercises = get_dialogue_exercises(topic_id, major, sub) if major and sub else get_dialogue_exercises(topic_id)
    return jsonify(exercises)


# ============= CULTURE API ENDPOINTS =============

@app.route('/api/culture/topics')
def api_culture_topics():
    """Get all culture topics for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    topics = get_culture_topics(major, sub) if major and sub else get_culture_topics()
    return jsonify(topics)


@app.route('/api/culture/<topic_id>')
def api_culture_topic(topic_id):
    """Get one culture topic with full content and questions if present."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    topic = get_culture_topic(topic_id, major, sub) if major and sub else get_culture_topic(topic_id)
    if not topic:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(topic)


# ============= EXERCISES API ENDPOINTS =============

@app.route('/api/exercises/sets')
def api_exercise_sets():
    """Get all exercise sets for current level or specified level."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    sets = get_exercise_sets(major, sub) if major and sub else get_exercise_sets()
    return jsonify(sets)


@app.route('/api/exercises/<set_id>')
def api_exercise_set(set_id):
    """Get one exercise set (metadata only)."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    data = get_exercise_set(set_id, major, sub) if major and sub else get_exercise_set(set_id)
    if not data:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(data)


@app.route('/api/exercises/<set_id>/tasks')
def api_exercise_tasks(set_id):
    """Get tasks for an exercise set."""
    major = request.args.get('major')
    sub = request.args.get('sub')

    tasks = get_exercise_tasks(set_id, major, sub) if major and sub else get_exercise_tasks(set_id)
    return jsonify(tasks)


# ============= PROGRESS API ENDPOINTS =============

@app.route('/api/progress/phrase', methods=['POST'])
def api_update_phrase_progress():
    """Update phrase progress."""
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        asyncio.run(get_or_create_user(user_id, None, None))

        is_correct = data.get('is_correct', False)
        asyncio.run(save_phrase_progress(
            user_id, data['phrase_id'], data['category_id'], is_correct
        ))

        words = 1 if is_correct else 0
        correct = 1 if is_correct else 0
        asyncio.run(update_daily_stats(user_id, words=words, correct=correct, total=1))

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving phrase progress for user {user_id}: {e}")
        return jsonify({'error': 'Failed to save progress'}), 500


@app.route('/api/progress/dialogue', methods=['POST'])
def api_update_dialogue_progress():
    """Update dialogue progress."""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    # Убеждаемся, что пользователь существует в базе
    try:
        asyncio.run(get_or_create_user(user_id, None, None))
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
        # Продолжаем выполнение, так как пользователь может уже существовать
    
    exercises_completed = data.get('exercises_completed', 0)
    exercises_correct = data.get('exercises_correct', 0)
    
    # Обновляем dialogue_progress таблицу
    asyncio.run(save_dialogue_progress(
        user_id, data['dialogue_id'], 
        exercises_completed, exercises_correct
    ))
    
    # Обновляем daily_stats (диалоги считаем как тесты)
    asyncio.run(update_daily_stats(
        user_id, 
        tests=1,  # один диалог = один тест
        correct=exercises_correct, 
        total=exercises_completed
    ))
    
    return jsonify({'success': True})


@app.route('/api/progress/culture', methods=['POST'])
def api_update_culture_progress():
    """Update culture topic progress (view and/or quiz result)."""
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        asyncio.run(get_or_create_user(user_id, None, None))
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")

    major = data.get('major')
    sub = data.get('sub')
    if not major or not sub:
        major, sub = get_current_level()

    topic_id = data.get('topic_id')
    if not topic_id:
        return jsonify({'error': 'topic_id required'}), 400

    quiz_completed = data.get('quiz_completed', 0)
    quiz_correct = data.get('quiz_correct', 0)
    quiz_total = data.get('quiz_total', 0)

    # viewed_at не принимается от клиента — сервер всегда использует datetime.now()
    asyncio.run(save_culture_progress(
        user_id, topic_id, major, sub,
        viewed_at=None,
        quiz_completed=quiz_completed,
        quiz_correct=quiz_correct,
        quiz_total=quiz_total
    ))
    return jsonify({'success': True})


@app.route('/api/progress/exercise', methods=['POST'])
def api_update_exercise_progress():
    """Update exercise set progress."""
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        asyncio.run(get_or_create_user(user_id, None, None))
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")

    major = data.get('major')
    sub = data.get('sub')
    if not major or not sub:
        major, sub = get_current_level()

    set_id = data.get('set_id')
    if not set_id:
        return jsonify({'error': 'set_id required'}), 400

    tasks_completed = data.get('tasks_completed', 0)
    tasks_correct = data.get('tasks_correct', 0)

    asyncio.run(save_exercise_set_progress(
        user_id, set_id, major, sub, tasks_completed, tasks_correct
    ))
    asyncio.run(update_daily_stats(
        user_id, tests=1, correct=tasks_correct, total=tasks_completed
    ))
    return jsonify({'success': True})


# ============= FEEDBACK API ENDPOINTS =============

@app.route('/api/feedback', methods=['GET'])
def api_get_feedback():
    """Get user's feedback list."""
    user_id = request.args.get('user_id', type=int)
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        feedback_list = asyncio.run(get_user_feedback(user_id, limit=10))
        total = asyncio.run(get_feedback_count(user_id))
        
        return jsonify({
            'feedback': feedback_list,
            'total': total
        })
    except Exception as e:
        logger.error(f"Error getting feedback for user {user_id}: {e}")
        return jsonify({'error': 'Failed to load feedback'}), 500


@app.route('/api/feedback', methods=['POST'])
def api_submit_feedback():
    """Submit new feedback."""
    data = request.json
    user_id = data.get('user_id')
    text = data.get('text', '').strip()
    
    if not user_id:
        return jsonify({'error': 'User not authenticated', 'success': False}), 401
    
    if not text:
        return jsonify({'error': 'Text is required', 'success': False}), 400
    
    if len(text) > MAX_FEEDBACK_LENGTH:
        return jsonify({
            'error': f'Text too long. Maximum {MAX_FEEDBACK_LENGTH} characters.',
            'success': False
        }), 400
    
    try:
        # Ensure user exists
        asyncio.run(get_or_create_user(user_id, None, None))
        
        # Save feedback
        feedback_id = asyncio.run(save_feedback(user_id, text))
        
        logger.info(f"User {user_id} submitted feedback #{feedback_id}")
        
        return jsonify({
            'success': True,
            'feedback_id': feedback_id
        })
    except Exception as e:
        logger.error(f"Error saving feedback for user {user_id}: {e}")
        return jsonify({'error': 'Failed to save feedback', 'success': False}), 500


@app.route('/api/feedback/status-labels')
def api_feedback_status_labels():
    """Get feedback status labels."""
    return jsonify(FEEDBACK_STATUS_LABELS)


# ============= TELEGRAM BOT WEBHOOK ENDPOINTS =============

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates via webhook."""
    global bot_application

    async def _process_webhook():
        """Process webhook in async context."""
        try:
            logger.info("Webhook: Starting request processing...")
            
            # Check if DATABASE_URL is set
            if not DATABASE_URL:
                logger.error("Webhook: DATABASE_URL is not set!")
                return 'Database not configured', 500
            
            logger.info(f"Webhook: DATABASE_URL is set (prefix: {DATABASE_URL[:20]}...)")

            # Ensure bot is initialized
            if bot_application is None:
                logger.info("Webhook: Bot not initialized, starting initialization...")
                try:
                    await init_bot()
                    logger.info("Webhook: Bot initialized successfully")
                except Exception as init_error:
                    logger.error(f"Webhook: Bot initialization failed: {init_error}", exc_info=True)
                    return 'OK', 200  # Return OK to avoid retries

            # Parse the update
            update_data = request.get_json()
            logger.info(f"Webhook: Received update data: {str(update_data)[:200]}...")
            
            if not update_data:
                logger.warning("Webhook: Empty update data received")
                return 'OK', 200

            update = Update.de_json(update_data, bot_application.bot)
            logger.info(f"Webhook: Parsed update, type: {update.effective_message.text if update.effective_message else 'callback'}")

            # Process the update synchronously
            logger.info("Webhook: Processing update...")
            await bot_application.process_update(update)
            logger.info("Webhook: Update processed successfully")
            
            return 'OK', 200
        except Exception as e:
            logger.error(f"Webhook: Error processing: {e}", exc_info=True)
            # Still return OK to Telegram to avoid retries
            return 'OK', 200
    
    # Use asyncio.run() which creates a new event loop for each call
    # nest_asyncio allows this to work even if there's already a loop
    # Each request gets its own event loop and connection pool
    try:
        return asyncio.run(_process_webhook())
    except Exception as e:
        logger.error(f"Error in webhook event loop: {e}", exc_info=True)
        # Return OK to prevent Telegram from retrying
        return 'OK', 200


@app.route('/setup-webhook')
def setup_webhook():
    """Setup webhook URL with Telegram. Call once after deploy."""
    import requests

    # Get the external URL from environment or construct it
    render_url = os.getenv('RENDER_EXTERNAL_URL', '')
    if not render_url:
        # Try to get from request
        render_url = request.host_url.rstrip('/')

    webhook_url = f"{render_url}/webhook"

    try:
        # Set webhook via Telegram API
        response = requests.get(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook',
            params={'url': webhook_url},
            timeout=10
        )
        result = response.json()

        if result.get('ok'):
            logger.info(f"Webhook set successfully to: {webhook_url}")
        else:
            logger.error(f"Failed to set webhook: {result}")

        return jsonify({
            'webhook_url': webhook_url,
            'telegram_response': result
        })
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/webhook-info')
def webhook_info():
    """Get current webhook info from Telegram."""
    import requests

    try:
        response = requests.get(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo',
            timeout=10
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot_initialized': bot_application is not None
    })


@app.route('/debug')
def debug_info():
    """Debug endpoint to check configuration and database connection."""
    import sys
    
    debug_data = {
        'python_version': sys.version,
        'telegram_token_set': bool(TELEGRAM_BOT_TOKEN),
        'telegram_token_prefix': TELEGRAM_BOT_TOKEN[:10] + '...' if TELEGRAM_BOT_TOKEN else None,
        'database_url_set': bool(DATABASE_URL),
        'database_url_prefix': DATABASE_URL[:30] + '...' if DATABASE_URL else None,
        'bot_initialized': bot_application is not None,
        'environment': {
            'RENDER': os.getenv('RENDER'),
            'RENDER_EXTERNAL_URL': os.getenv('RENDER_EXTERNAL_URL'),
            'PORT': os.getenv('PORT'),
        }
    }
    
    # Test database connection
    async def test_db():
        try:
            from bot.database import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchval('SELECT 1')
                return {'db_connection': 'OK', 'test_query': result}
        except Exception as e:
            return {'db_connection': 'FAILED', 'db_error': str(e), 'db_error_type': type(e).__name__}
    
    try:
        db_result = asyncio.run(test_db())
        debug_data.update(db_result)
    except Exception as e:
        debug_data['db_connection'] = 'FAILED'
        debug_data['db_error'] = str(e)
        debug_data['db_error_type'] = type(e).__name__
    
    return jsonify(debug_data)


@app.route('/debug/init-bot')
def debug_init_bot():
    """Debug endpoint to manually initialize bot and see errors."""
    async def _init():
        try:
            logger.info("Debug: Starting bot initialization...")
            
            # Check DATABASE_URL
            if not DATABASE_URL:
                return {'error': 'DATABASE_URL is not set'}
            
            logger.info(f"Debug: DATABASE_URL prefix: {DATABASE_URL[:30]}...")
            
            # Try to initialize database
            logger.info("Debug: Initializing database...")
            await init_db()
            logger.info("Debug: Database initialized")
            
            # Try to create bot application
            logger.info("Debug: Creating bot application...")
            global bot_application
            if bot_application is None:
                bot_application = create_bot_application()
                await bot_application.initialize()
            logger.info("Debug: Bot application created")
            
            return {
                'status': 'OK',
                'bot_initialized': True,
                'message': 'Bot initialized successfully'
            }
        except Exception as e:
            logger.error(f"Debug init error: {e}", exc_info=True)
            return {
                'status': 'FAILED',
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    try:
        result = asyncio.run(_init())
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'FAILED',
            'error': str(e),
            'error_type': type(e).__name__
        })


# ============= APPLICATION STARTUP =============

# Initialize on module load for gunicorn
init_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    is_production = os.getenv('RENDER') is not None
    app.run(host='0.0.0.0', port=port, debug=not is_production)
