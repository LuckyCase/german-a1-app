"""
Web server for Telegram Web App + Bot Webhook
Combined server for Render free tier (single web service)
"""
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os
import asyncio
import logging
import nest_asyncio

# Allow nested event loops (needed for Flask + asyncpg)
nest_asyncio.apply()

from bot.content_manager import (
    get_all_words, get_categories, get_words_by_category, 
    get_all_tests, get_test_questions, init_content,
    get_phrases_categories, get_phrases_by_category,
    get_dialogue_topics, get_dialogue, get_dialogue_exercises
)
from bot.database import (
    get_user_stats, update_word_progress, save_grammar_result, 
    update_daily_stats, init_db, save_phrase_progress, save_dialogue_progress
)
from bot.config import TELEGRAM_BOT_TOKEN, DATABASE_URL

# Telegram bot imports
from telegram import Update
from telegram.ext import Application, CommandHandler

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


def create_bot_application():
    """Create and configure the bot application."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Only /start command - everything else is in Web App
    application.add_handler(CommandHandler("start", start))

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
            max-width: 480px;
            margin: 0 auto;
            padding: 16px;
            padding-bottom: 100px;
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
        }
        
        .header::before {
            content: '🇩🇪';
            position: absolute;
            font-size: 120px;
            opacity: 0.05;
            right: -20px;
            top: -20px;
        }
        
        .header h1 {
            font-size: clamp(1.5rem, 5vw, 1.8rem);
            font-weight: 800;
            background: linear-gradient(135deg, #fff 0%, #c7d2fe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 4px;
        }
        
        .header p {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        /* Navigation tabs */
        .nav {
            display: flex;
            gap: 8px;
            padding: 6px;
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
        }
        
        .nav-tab {
            flex: 1;
            padding: 12px 8px;
            background: transparent;
            border: none;
            border-radius: var(--radius-md);
            font-family: inherit;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }
        
        .nav-tab span {
            font-size: 1.2rem;
        }
        
        .nav-tab.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
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
            color: var(--tg-theme-hint-color, var(--text-secondary));
            font-size: 0.85rem;
            background: var(--tg-theme-button-color, rgba(99, 102, 241, 0.2));
            padding: 4px 10px;
            border-radius: 20px;
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
            color: var(--tg-theme-hint-color, var(--text-secondary));
            margin-bottom: 16px;
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
        
        /* Progress stats */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .stat-card {
            background: var(--tg-theme-secondary-bg-color, var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 20px 16px;
            text-align: center;
            color: var(--tg-theme-text-color, var(--text-primary));
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--primary-light) 0%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
            margin-top: 4px;
        }
        
        /* Progress bar */
        .progress-bar {
            height: 12px;
            background: var(--bg-secondary);
            border-radius: 10px;
            overflow: hidden;
            margin-top: 20px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--primary-light));
            border-radius: 10px;
            transition: width 0.5s ease;
            position: relative;
        }
        
        .progress-text {
            text-align: center;
            margin-top: 8px;
            font-size: 0.85rem;
            color: var(--tg-theme-hint-color, var(--text-secondary));
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
            color: var(--primary-light);
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
            .nav-tab { padding: 10px 6px; font-size: 0.75rem; }
        }
        
        @media (min-width: 481px) {
            .app { padding: 24px; }
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
        <header class="header">
            <h1>German A1</h1>
            <p>Учи немецкий легко и эффективно</p>
        </header>
        
        <nav class="nav">
            <button class="nav-tab active" data-tab="flashcards">
                <span>📚</span>
                Слова
            </button>
            <button class="nav-tab" data-tab="grammar">
                <span>📝</span>
                Грамматика
            </button>
            <button class="nav-tab" data-tab="phrases">
                <span>💬</span>
                Фразы
            </button>
            <button class="nav-tab" data-tab="dialogues">
                <span>🗣️</span>
                Диалоги
            </button>
            <button class="nav-tab" data-tab="progress">
                <span>📊</span>
                Прогресс
            </button>
        </nav>
        
        <!-- Flashcards Section -->
        <section id="flashcards" class="section active">
            <div id="categories-view">
                <div class="card">
                    <h2 class="card-title">Выберите категорию</h2>
                    <div id="categories-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="flashcard-view" style="display: none;">
                <button class="back-btn" onclick="backToCategories()">← Назад к категориям</button>
                
                <div class="flashcard">
                    <div class="flashcard-progress" id="word-progress">Слово 1 из 10</div>
                    <div class="flashcard-word" id="word-de">Wort</div>
                    <div class="flashcard-example" id="word-example">Beispiel</div>
                    <button class="audio-btn" id="audio-btn" onclick="playAudio()">
                        🔊 Прослушать
                    </button>
                </div>
                
                <div class="options" id="word-options"></div>
                
                <button class="btn btn-primary" id="next-btn" style="display: none; margin-top: 16px;" onclick="nextWord()">
                    Следующее слово →
                </button>
            </div>
        </section>
        
        <!-- Grammar Section -->
        <section id="grammar" class="section">
            <div id="tests-view">
                <div class="card">
                    <h2 class="card-title">Выберите тест</h2>
                    <div id="tests-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="grammar-view" style="display: none;">
                <button class="back-btn" onclick="backToTests()">← Назад к тестам</button>
                
                <div class="question-card">
                    <div class="question-number" id="question-number">Вопрос 1 из 10</div>
                    <div class="question-text" id="question-text">Вопрос...</div>
                </div>
                
                <div class="options" id="question-options"></div>
                
                <button class="btn btn-primary" id="next-question-btn" style="display: none; margin-top: 16px;" onclick="nextQuestion()">
                    Следующий вопрос →
                </button>
            </div>
        </section>
        
        <!-- Phrases Section -->
        <section id="phrases" class="section">
            <div id="phrases-categories-view">
                <div class="card">
                    <h2 class="card-title">Выберите категорию</h2>
                    <div id="phrases-categories-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="phrases-view" style="display: none;">
                <button class="back-btn" onclick="backToPhrasesCategories()">← Назад</button>
                <div class="flashcard">
                    <div class="flashcard-progress" id="phrase-progress">Фраза 1 из 10</div>
                    <div class="flashcard-word" id="phrase-de">Phrase</div>
                    <div class="flashcard-example" id="phrase-context">Context</div>
                    <div class="flashcard-example" id="phrase-example" style="margin-top: 8px;"></div>
                    <button class="audio-btn" onclick="playPhraseAudio()">🔊 Прослушать</button>
                </div>
                <div class="options" id="phrase-options"></div>
                <button class="btn btn-primary" id="next-phrase-btn" style="display: none; margin-top: 16px;" onclick="nextPhrase()">
                    Следующая фраза →
                </button>
            </div>
        </section>
        
        <!-- Dialogues Section -->
        <section id="dialogues" class="section">
            <div id="dialogues-topics-view">
                <div class="card">
                    <h2 class="card-title">Выберите диалог</h2>
                    <div id="dialogues-topics-list" class="btn-group">
                        <div class="loading">Загрузка...</div>
                    </div>
                </div>
            </div>
            
            <div id="dialogue-view" style="display: none;">
                <button class="back-btn" onclick="backToDialoguesTopics()">← Назад</button>
                <div id="dialogue-content" class="card"></div>
                <button class="btn btn-primary" id="dialogue-exercise-btn" style="margin-top: 16px;" onclick="showDialogueExercise()">
                    Упражнение →
                </button>
            </div>
            
            <div id="dialogue-exercise-view" style="display: none;">
                <button class="back-btn" onclick="backToDialogue()">← Назад к диалогу</button>
                <div class="question-card">
                    <div class="question-number" id="exercise-number">Упражнение 1 из 3</div>
                    <div class="question-text" id="exercise-question"></div>
                </div>
                <div class="options" id="exercise-options"></div>
                <button class="btn btn-primary" id="next-exercise-btn" style="display: none; margin-top: 16px;" onclick="nextExercise()">
                    Следующее упражнение →
                </button>
            </div>
        </section>
        
        <!-- Progress Section -->
        <section id="progress" class="section">
            <div class="card">
                <h2 class="card-title">Ваша статистика</h2>
                <div id="progress-stats">
                    <div class="loading">Загрузка...</div>
                </div>
            </div>
        </section>
    </div>
    
    <audio id="word-audio"></audio>
    
    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        tg.enableClosingConfirmation();
        
        // Apply Telegram theme
        document.documentElement.style.setProperty('--bg-primary', tg.themeParams.bg_color || '#0f0f23');
        document.documentElement.style.setProperty('--bg-secondary', tg.themeParams.secondary_bg_color || '#1a1a2e');
        document.documentElement.style.setProperty('--text-primary', tg.themeParams.text_color || '#ffffff');
        document.documentElement.style.setProperty('--text-secondary', tg.themeParams.hint_color || '#a0a0b0');
        
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
        
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.dataset.tab;
                
                document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
                
                tab.classList.add('active');
                document.getElementById(tabId).classList.add('active');
                
                if (tabId === 'phrases') loadPhrasesCategories();
                if (tabId === 'dialogues') loadDialoguesTopics();
                if (tabId === 'progress') loadProgress();
                
                tg.HapticFeedback.selectionChanged();
            });
        });
        
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
                const response = await fetch(`/api/words?category=${categoryId}`);
                currentWords = await response.json();
                currentWordIndex = 0;
                currentCategory = categoryId;
                
                document.getElementById('categories-view').style.display = 'none';
                document.getElementById('flashcard-view').style.display = 'block';
                
                showNextWord();
            } catch (error) {
                tg.showAlert('Ошибка загрузки слов');
            }
        }
        
        function backToCategories() {
            document.getElementById('flashcard-view').style.display = 'none';
            document.getElementById('categories-view').style.display = 'block';
        }
        
        async function showNextWord() {
            if (currentWordIndex >= currentWords.length) {
                tg.showAlert(`🎉 Отлично! Изучено ${currentWords.length} слов!`);
                backToCategories();
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
            
            // Get options
            const response = await fetch('/api/words/random?count=3&exclude=' + word.word_id);
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
                audio.play().catch(() => tg.showAlert('Ошибка воспроизведения'));
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
                        tg.showAlert('Ошибка воспроизведения');
                        audioBtn.textContent = '🔊 Прослушать';
                    });
                };
                
                audio.onerror = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    tg.showAlert('Ошибка загрузки аудио');
                };
                
                audio.load();
            } catch (error) {
                audioBtn.textContent = '🔊 Прослушать';
                audioBtn.disabled = false;
            }
        }
        
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
            
            tg.HapticFeedback.notificationOccurred(isCorrect ? 'success' : 'error');
            document.getElementById('next-btn').style.display = 'block';
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
                tg.showAlert('Ошибка загрузки теста');
            }
        }
        
        function backToTests() {
            document.getElementById('grammar-view').style.display = 'none';
            document.getElementById('tests-view').style.display = 'block';
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
            tg.HapticFeedback.notificationOccurred(isCorrect ? 'success' : 'error');
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
            
            tg.showAlert(`🎉 Тест завершён!\\nРезультат: ${userScore} из ${total} (${percentage}%)`);
            backToTests();
        }
        
        // Progress
        async function loadProgress() {
            try {
                const response = await fetch(`/api/progress?user_id=${userId}`);
                const stats = await response.json();
                const accuracy = stats.total_correct + stats.total_wrong > 0 
                    ? Math.round((stats.total_correct / (stats.total_correct + stats.total_wrong)) * 100) 
                    : 0;
                
                document.getElementById('progress-stats').innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${stats.total_words || 0}</div>
                            <div class="stat-label">Изучено слов</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.mastered_words || 0}</div>
                            <div class="stat-label">Освоено</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.tests_completed || 0}</div>
                            <div class="stat-label">Тестов</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${accuracy}%</div>
                            <div class="stat-label">Точность</div>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${Math.min(100, (stats.total_words || 0) / 2)}%"></div>
                    </div>
                    <div class="progress-text">Прогресс изучения: ${stats.total_words || 0} / 200 слов</div>
                `;
            } catch (error) {
                document.getElementById('progress-stats').innerHTML = 
                    '<div class="error-msg">Ошибка загрузки статистики</div>';
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
        
        async function startPhrases(categoryId) {
            try {
                const response = await fetch(`/api/phrases?category=${categoryId}`);
                currentPhrases = await response.json();
                currentPhraseIndex = 0;
                currentPhrasesCategory = categoryId;
                
                document.getElementById('phrases-categories-view').style.display = 'none';
                document.getElementById('phrases-view').style.display = 'block';
                
                showNextPhrase();
            } catch (error) {
                tg.showAlert('Ошибка загрузки фраз');
            }
        }
        
        function backToPhrasesCategories() {
            document.getElementById('phrases-view').style.display = 'none';
            document.getElementById('phrases-categories-view').style.display = 'block';
        }
        
        function showNextPhrase() {
            if (currentPhraseIndex >= currentPhrases.length) {
                tg.showAlert(`🎉 Отлично! Изучено ${currentPhrases.length} фраз!`);
                backToPhrasesCategories();
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
            
            // Get options (random phrases from other categories)
            fetch('/api/phrases/categories')
                .then(r => r.json())
                .then(categories => {
                    const otherCategories = categories.filter(c => c.id !== currentPhrasesCategory);
                    const randomCategory = otherCategories[Math.floor(Math.random() * otherCategories.length)];
                    if (randomCategory) {
                        fetch(`/api/phrases?category=${randomCategory.id}`)
                            .then(r => r.json())
                            .then(wrongPhrases => {
                                const options = [phrase, ...wrongPhrases.slice(0, 2)].sort(() => Math.random() - 0.5);
                                const optionsDiv = document.getElementById('phrase-options');
                                optionsDiv.innerHTML = '';
                                
                                options.forEach((opt) => {
                                    const btn = document.createElement('button');
                                    btn.className = 'option';
                                    btn.textContent = opt.ru;
                                    btn.onclick = () => selectPhraseAnswer(btn, opt.phrase_id === phrase.phrase_id, phrase.ru);
                                    optionsDiv.appendChild(btn);
                                });
                            });
                    }
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
                audio.play().catch(() => tg.showAlert('Ошибка воспроизведения'));
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
                        tg.showAlert('Ошибка воспроизведения');
                        audioBtn.textContent = '🔊 Прослушать';
                    });
                };
                
                audio.onerror = () => {
                    audioBtn.textContent = '🔊 Прослушать';
                    audioBtn.disabled = false;
                    tg.showAlert('Ошибка загрузки аудио');
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
            
            tg.HapticFeedback.notificationOccurred(isCorrect ? 'success' : 'error');
            document.getElementById('next-phrase-btn').style.display = 'block';
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
                tg.showAlert('Ошибка загрузки диалога');
            }
        }
        
        function backToDialoguesTopics() {
            document.getElementById('dialogue-view').style.display = 'none';
            document.getElementById('dialogue-exercise-view').style.display = 'none';
            document.getElementById('dialogues-topics-view').style.display = 'block';
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
                    tg.showAlert('Упражнения для этого диалога пока не готовы');
                    return;
                }
                
                document.getElementById('dialogue-view').style.display = 'none';
                document.getElementById('dialogue-exercise-view').style.display = 'block';
                
                showNextExercise();
            } catch (error) {
                tg.showAlert('Ошибка загрузки упражнений');
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
            tg.HapticFeedback.notificationOccurred(isCorrect ? 'success' : 'error');
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
            
            tg.showAlert(`🎉 Упражнение завершено!\\nРезультат: ${exerciseScore} из ${total} (${percentage}%)`);
            backToDialogue();
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

@app.route('/api/categories')
def api_categories():
    categories = get_categories()
    return jsonify(categories)

@app.route('/api/words')
def api_words():
    category_id = request.args.get('category')
    if category_id and category_id != 'all':
        words = get_words_by_category(category_id)
    else:
        words = get_all_words()
    return jsonify(words)

@app.route('/api/words/random')
def api_random_words():
    count = int(request.args.get('count', 3))
    exclude = request.args.get('exclude', '')
    all_words = get_all_words()
    filtered = [w for w in all_words if w.get('word_id') != exclude]
    import random
    return jsonify(random.sample(filtered, min(count, len(filtered))))

@app.route('/api/tests')
def api_tests():
    tests = get_all_tests()
    return jsonify(tests)

@app.route('/api/tests/<test_id>/questions')
def api_test_questions(test_id):
    questions = get_test_questions(test_id)
    return jsonify(questions)

@app.route('/api/progress')
def api_progress():
    # Get user_id from query parameter (sent from frontend)
    user_id = request.args.get('user_id', type=int)
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    stats = asyncio.run(get_user_stats(user_id))
    total_vocab = len(get_all_words())
    
    words_percentage = (stats["total_words"] / total_vocab * 100) if total_vocab > 0 else 0
    accuracy = (stats["total_correct"] / (stats["total_correct"] + stats["total_wrong"]) * 100) if (stats["total_correct"] + stats["total_wrong"]) > 0 else 0
    
    return jsonify({
        **stats,
        'words_percentage': words_percentage,
        'accuracy': accuracy
    })

@app.route('/api/progress/word', methods=['POST'])
def api_update_word_progress():
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    is_correct = data.get('is_correct', False)
    
    # Обновляем progress таблицу
    asyncio.run(update_word_progress(user_id, data['word_id'], is_correct))
    
    # Обновляем daily_stats: words=1 только если правильно, correct=1/0, total=1
    words = 1 if is_correct else 0
    correct = 1 if is_correct else 0
    asyncio.run(update_daily_stats(user_id, words=words, correct=correct, total=1))
    
    return jsonify({'success': True})

@app.route('/api/progress/grammar', methods=['POST'])
def api_save_grammar_result():
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    asyncio.run(save_grammar_result(user_id, data['test_id'], data['score'], data['total']))
    asyncio.run(update_daily_stats(user_id, tests=1, correct=data['score'], total=data['total']))
    return jsonify({'success': True})

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
    """Get all phrases categories."""
    categories = get_phrases_categories()
    return jsonify(categories)


@app.route('/api/phrases')
def api_phrases():
    """Get phrases by category."""
    category_id = request.args.get('category')
    phrases = get_phrases_by_category(category_id) if category_id else []
    return jsonify(phrases)


# ============= DIALOGUES API ENDPOINTS =============

@app.route('/api/dialogues/topics')
def api_dialogue_topics():
    """Get all dialogue topics."""
    topics = get_dialogue_topics()
    return jsonify(topics)


@app.route('/api/dialogues/<topic_id>')
def api_dialogue(topic_id):
    """Get dialogue by topic ID."""
    dialogue = get_dialogue(topic_id)
    return jsonify(dialogue) if dialogue else jsonify({'error': 'Not found'}), 404


@app.route('/api/dialogues/<topic_id>/exercises')
def api_dialogue_exercises(topic_id):
    """Get exercises for dialogue."""
    exercises = get_dialogue_exercises(topic_id)
    return jsonify(exercises)


# ============= PROGRESS API ENDPOINTS =============

@app.route('/api/progress/phrase', methods=['POST'])
def api_update_phrase_progress():
    """Update phrase progress."""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    is_correct = data.get('is_correct', False)
    
    # Обновляем phrase_progress таблицу
    asyncio.run(save_phrase_progress(
        user_id, data['phrase_id'], data['category_id'], is_correct
    ))
    
    # Обновляем daily_stats (фразы считаем как слова)
    words = 1 if is_correct else 0
    correct = 1 if is_correct else 0
    asyncio.run(update_daily_stats(user_id, words=words, correct=correct, total=1))
    
    return jsonify({'success': True})


@app.route('/api/progress/dialogue', methods=['POST'])
def api_update_dialogue_progress():
    """Update dialogue progress."""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
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
    app.run(host='0.0.0.0', port=port, debug=True)
