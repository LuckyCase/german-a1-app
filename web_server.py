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

from bot.data.vocabulary import get_all_words, get_categories, get_words_by_category
from bot.data.grammar import get_all_tests, get_test_questions
from bot.database import get_user_stats, update_word_progress, save_grammar_result, update_daily_stats, init_db
from bot.config import TELEGRAM_BOT_TOKEN, DATABASE_URL

# Telegram bot imports
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.handlers.common import start, help_command, menu_callback
from bot.handlers.flashcards import get_flashcards_handler
from bot.handlers.grammar import get_grammar_handler
from bot.handlers.progress import show_progress, progress_callback
from bot.handlers.reminders import reminder_settings, reminder_callback
from bot.handlers.audio import audio_command

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

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("progress", show_progress))
    application.add_handler(CommandHandler("reminder", reminder_settings))
    application.add_handler(CommandHandler("audio", audio_command))

    # Add callback handlers
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(progress_callback, pattern="^(progress_|start_flashcards|start_grammar)"))
    application.add_handler(CallbackQueryHandler(reminder_callback, pattern="^rem_"))

    # Add conversation handlers
    application.add_handler(get_flashcards_handler())
    application.add_handler(get_grammar_handler())

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
    # Don't initialize bot here - do it lazily on first webhook request
    # This avoids event loop conflicts with gunicorn workers
    logger.info("Application ready - bot will be initialized on first request")

# Read HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>German A1 Bot - Web App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #000000);
            padding: 0;
            margin: 0;
        }
        
        .container {
            max-width: 100%;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            padding: 20px;
            background: var(--tg-theme-header-bg-color, linear-gradient(135deg, #667eea 0%, #764ba2 100%));
            color: var(--tg-theme-header-text-color, #ffffff);
            border-radius: 15px;
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 1.8em;
            margin-bottom: 10px;
        }
        
        .tabs {
            display: flex;
            background: var(--tg-theme-secondary-bg-color, #f1f3f5);
            border-radius: 10px;
            padding: 5px;
            margin-bottom: 20px;
            overflow-x: auto;
        }
        
        .tab {
            flex: 1;
            padding: 12px;
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 600;
            color: var(--tg-theme-hint-color, #6c757d);
            border-radius: 8px;
            transition: all 0.3s;
            white-space: nowrap;
        }
        
        .tab.active {
            background: var(--tg-theme-button-color, #667eea);
            color: var(--tg-theme-button-text-color, #ffffff);
        }
        
        .tab-content {
            display: none;
            animation: fadeIn 0.3s;
        }
        
        .tab-content.active {
            display: block;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .card {
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
        }
        
        .card h3 {
            color: var(--tg-theme-link-color, #667eea);
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .button {
            background: var(--tg-theme-button-color, #667eea);
            color: var(--tg-theme-button-text-color, #ffffff);
            border: none;
            padding: 15px 20px;
            border-radius: 10px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
            transition: opacity 0.3s;
        }
        
        .button:active {
            opacity: 0.8;
        }
        
        .button-secondary {
            background: var(--tg-theme-secondary-bg-color, #e9ecef);
            color: var(--tg-theme-text-color, #000000);
        }
        
        .word-item {
            background: var(--tg-theme-bg-color, #ffffff);
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            border-left: 4px solid var(--tg-theme-button-color, #667eea);
        }
        
        .word-item h4 {
            font-size: 1.3em;
            margin-bottom: 5px;
            color: var(--tg-theme-text-color, #000000);
        }
        
        .word-item p {
            color: var(--tg-theme-hint-color, #6c757d);
            font-size: 0.9em;
            margin: 5px 0;
        }
        
        .options {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 15px;
        }
        
        .option-button {
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            color: var(--tg-theme-text-color, #000000);
            border: 2px solid var(--tg-theme-button-color, #667eea);
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .option-button:active {
            background: var(--tg-theme-button-color, #667eea);
            color: var(--tg-theme-button-text-color, #ffffff);
        }
        
        .option-button.correct {
            background: #51cf66;
            color: white;
            border-color: #51cf66;
        }
        
        .option-button.wrong {
            background: #ff6b6b;
            color: white;
            border-color: #ff6b6b;
        }
        
        .progress-bar {
            background: var(--tg-theme-secondary-bg-color, #e9ecef);
            height: 25px;
            border-radius: 12px;
            overflow: hidden;
            margin: 15px 0;
        }
        
        .progress-fill {
            background: var(--tg-theme-button-color, #667eea);
            height: 100%;
            width: 0%;
            transition: width 0.5s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin: 15px 0;
        }
        
        .stat-item {
            background: var(--tg-theme-bg-color, #ffffff);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-item .number {
            font-size: 2em;
            font-weight: bold;
            color: var(--tg-theme-button-color, #667eea);
        }
        
        .stat-item .label {
            font-size: 0.9em;
            color: var(--tg-theme-hint-color, #6c757d);
            margin-top: 5px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--tg-theme-hint-color, #6c757d);
        }
        
        .error {
            background: #ff6b6b;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
        }
        
        .button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        #audio-button {
            width: auto;
            display: inline-block;
            padding: 10px 15px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🇩🇪 German A1 Bot</h1>
            <p>Изучайте немецкий язык легко!</p>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="openTab('flashcards')">📚 Слова</button>
            <button class="tab" onclick="openTab('grammar')">📝 Грамматика</button>
            <button class="tab" onclick="openTab('progress')">📊 Прогресс</button>
        </div>
        
        <!-- Flashcards Tab -->
        <div id="flashcards" class="tab-content active">
            <div class="card">
                <h3>Выберите категорию</h3>
                <div id="categories-list">
                    <div class="loading">Загрузка категорий...</div>
                </div>
            </div>
            <div id="flashcard-content" style="display: none;">
                <div class="word-item">
                    <h4 id="word-de"></h4>
                    <p id="word-example"></p>
                    <button class="button button-secondary" onclick="playAudio()" id="audio-button" style="margin-top: 10px;">
                        🔊 Прослушать
                    </button>
                    <audio id="word-audio" style="display: none;"></audio>
                </div>
                <div class="options" id="word-options"></div>
                <button class="button" onclick="nextWord()" id="next-button" style="display: none;">Следующее слово</button>
            </div>
        </div>
        
        <!-- Grammar Tab -->
        <div id="grammar" class="tab-content">
            <div class="card">
                <h3>Выберите тест</h3>
                <div id="tests-list">
                    <div class="loading">Загрузка тестов...</div>
                </div>
            </div>
            <div id="grammar-content" style="display: none;">
                <div class="card">
                    <h3 id="question-text"></h3>
                    <div class="options" id="question-options"></div>
                    <button class="button" onclick="nextQuestion()" id="next-question-button" style="display: none;">Следующий вопрос</button>
                </div>
            </div>
        </div>
        
        <!-- Progress Tab -->
        <div id="progress" class="tab-content">
            <div class="card">
                <h3>Ваш прогресс</h3>
                <div id="progress-stats">
                    <div class="loading">Загрузка статистики...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        // Get user ID from Telegram Web App
        const userId = tg.initDataUnsafe?.user?.id || tg.initDataUnsafe?.user_id;
        
        let currentCategory = null;
        let currentWords = [];
        let currentWordIndex = 0;
        let currentTest = null;
        let currentQuestions = [];
        let currentQuestionIndex = 0;
        let userScore = 0;
        
        function openTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            if (tabName === 'progress') {
                loadProgress();
            }
        }
        
        async function loadCategories() {
            try {
                const response = await fetch('/api/categories');
                const categories = await response.json();
                const list = document.getElementById('categories-list');
                list.innerHTML = '';
                
                categories.forEach(cat => {
                    const button = document.createElement('button');
                    button.className = 'button';
                    button.textContent = `${cat.name} (${cat.count} слов)`;
                    button.onclick = () => startFlashcards(cat.id);
                    list.appendChild(button);
                });
            } catch (error) {
                document.getElementById('categories-list').innerHTML = 
                    '<div class="error">Ошибка загрузки категорий</div>';
            }
        }
        
        async function startFlashcards(categoryId) {
            try {
                const response = await fetch(`/api/words?category=${categoryId}`);
                const words = await response.json();
                currentWords = words;
                currentWordIndex = 0;
                currentCategory = categoryId;
                document.getElementById('categories-list').style.display = 'none';
                document.getElementById('flashcard-content').style.display = 'block';
                showNextWord();
            } catch (error) {
                tg.showAlert('Ошибка загрузки слов');
            }
        }
        
        async function showNextWord() {
            if (currentWordIndex >= currentWords.length) {
                tg.showAlert(`Сессия завершена! Изучено ${currentWords.length} слов.`);
                document.getElementById('flashcard-content').style.display = 'none';
                document.getElementById('categories-list').style.display = 'block';
                return;
            }
            
            const word = currentWords[currentWordIndex];
            document.getElementById('word-de').textContent = word.de;
            document.getElementById('word-example').textContent = word.example || '';
            
            // Reset audio - remove event handlers first to prevent error triggers
            const audio = document.getElementById('word-audio');
            const audioButton = document.getElementById('audio-button');
            audio.pause();
            audio.onerror = null;
            audio.onloadeddata = null;
            audio.src = '';
            audioButton.textContent = '🔊 Прослушать';
            audioButton.disabled = false;
            
            // Get wrong options
            const response = await fetch('/api/words/random?count=3&exclude=' + word.word_id);
            const wrongWords = await response.json();
            
            const options = [word, ...wrongWords].sort(() => Math.random() - 0.5);
            const optionsDiv = document.getElementById('word-options');
            optionsDiv.innerHTML = '';
            
            options.forEach((opt, index) => {
                const button = document.createElement('button');
                button.className = 'option-button';
                button.textContent = opt.ru;
                button.onclick = () => selectAnswer(index, opt.word_id === word.word_id);
                optionsDiv.appendChild(button);
            });
            
            document.getElementById('next-button').style.display = 'none';
        }
        
        async function playAudio() {
            const word = currentWords[currentWordIndex];
            if (!word) return;
            
            const audio = document.getElementById('word-audio');
            const audioButton = document.getElementById('audio-button');
            
            // If audio is already loaded and playing, just play it
            if (audio.src && audio.src.includes(encodeURIComponent(word.de))) {
                audio.currentTime = 0;
                audio.play().catch(err => {
                    console.error('Error playing audio:', err);
                    tg.showAlert('Ошибка воспроизведения аудио');
                });
                return;
            }
            
            // Load audio from server
            audioButton.textContent = '⏳ Загрузка...';
            audioButton.disabled = true;
            
            try {
                const audioUrl = `/api/audio/${encodeURIComponent(word.de)}`;
                audio.src = audioUrl;
                
                audio.onloadeddata = () => {
                    audioButton.textContent = '🔊 Прослушать';
                    audioButton.disabled = false;
                    audio.play().catch(err => {
                        console.error('Error playing audio:', err);
                        tg.showAlert('Ошибка воспроизведения аудио');
                        audioButton.textContent = '🔊 Прослушать';
                        audioButton.disabled = false;
                    });
                };
                
                audio.onerror = () => {
                    audioButton.textContent = '🔊 Прослушать';
                    audioButton.disabled = false;
                    tg.showAlert('Ошибка загрузки аудио');
                };
                
                audio.load();
            } catch (error) {
                console.error('Error loading audio:', error);
                tg.showAlert('Ошибка загрузки аудио');
                audioButton.textContent = '🔊 Прослушать';
                audioButton.disabled = false;
            }
        }
        
        async function selectAnswer(optionIndex, isCorrect) {
            const buttons = document.querySelectorAll('.option-button');
            buttons.forEach((btn, idx) => {
                btn.onclick = null;
                if (idx === optionIndex) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (isCorrect && idx !== optionIndex) {
                    // Show correct answer
                    const word = currentWords[currentWordIndex];
                    if (btn.textContent === word.ru) {
                        btn.classList.add('correct');
                    }
                }
            });
            
            // Save progress
            const word = currentWords[currentWordIndex];
            await fetch('/api/progress/word', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    word_id: word.word_id,
                    is_correct: isCorrect
                })
            });
            
            if (isCorrect) {
                tg.HapticFeedback.notificationOccurred('success');
            } else {
                tg.HapticFeedback.notificationOccurred('error');
            }
            
            document.getElementById('next-button').style.display = 'block';
        }
        
        function nextWord() {
            currentWordIndex++;
            showNextWord();
        }
        
        async function loadTests() {
            try {
                const response = await fetch('/api/tests');
                const tests = await response.json();
                const list = document.getElementById('tests-list');
                list.innerHTML = '';
                
                tests.forEach(test => {
                    const button = document.createElement('button');
                    button.className = 'button';
                    button.textContent = `${test.name} (${test.questions_count} вопросов)`;
                    button.onclick = () => startTest(test.id);
                    list.appendChild(button);
                });
            } catch (error) {
                document.getElementById('tests-list').innerHTML = 
                    '<div class="error">Ошибка загрузки тестов</div>';
            }
        }
        
        async function startTest(testId) {
            try {
                const response = await fetch(`/api/tests/${testId}/questions`);
                const questions = await response.json();
                currentQuestions = questions;
                currentQuestionIndex = 0;
                currentTest = testId;
                userScore = 0;
                document.getElementById('tests-list').style.display = 'none';
                document.getElementById('grammar-content').style.display = 'block';
                showNextQuestion();
            } catch (error) {
                tg.showAlert('Ошибка загрузки теста');
            }
        }
        
        function showNextQuestion() {
            if (currentQuestionIndex >= currentQuestions.length) {
                finishTest();
                return;
            }
            
            const question = currentQuestions[currentQuestionIndex];
            document.getElementById('question-text').textContent = 
                `Вопрос ${currentQuestionIndex + 1} из ${currentQuestions.length}\n\n${question.question}`;
            
            const optionsDiv = document.getElementById('question-options');
            optionsDiv.innerHTML = '';
            
            question.options.forEach((option, index) => {
                const button = document.createElement('button');
                button.className = 'option-button';
                button.textContent = option;
                button.onclick = () => selectGrammarAnswer(index, question.correct === index);
                optionsDiv.appendChild(button);
            });
            
            document.getElementById('next-question-button').style.display = 'none';
        }
        
        async function selectGrammarAnswer(optionIndex, isCorrect) {
            const buttons = document.querySelectorAll('#question-options .option-button');
            buttons.forEach((btn, idx) => {
                btn.onclick = null;
                if (idx === optionIndex) {
                    btn.classList.add(isCorrect ? 'correct' : 'wrong');
                } else if (isCorrect && idx !== optionIndex) {
                    const question = currentQuestions[currentQuestionIndex];
                    if (idx === question.correct) {
                        btn.classList.add('correct');
                    }
                }
            });
            
            if (isCorrect) {
                userScore++;
                tg.HapticFeedback.notificationOccurred('success');
            } else {
                tg.HapticFeedback.notificationOccurred('error');
            }
            
            document.getElementById('next-question-button').style.display = 'block';
        }
        
        function nextQuestion() {
            currentQuestionIndex++;
            showNextQuestion();
        }
        
        async function finishTest() {
            const total = currentQuestions.length;
            const percentage = Math.round((userScore / total) * 100);
            
            // Save result
            await fetch('/api/progress/grammar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    test_id: currentTest,
                    score: userScore,
                    total: total
                })
            });
            
            tg.showAlert(`Тест завершён!\\nРезультат: ${userScore} из ${total} (${percentage}%)`);
            
            document.getElementById('grammar-content').style.display = 'none';
            document.getElementById('tests-list').style.display = 'block';
        }
        
        async function loadProgress() {
            try {
                const response = await fetch(`/api/progress?user_id=${userId}`);
                const stats = await response.json();
                
                const statsDiv = document.getElementById('progress-stats');
                statsDiv.innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="number">${stats.total_words}</div>
                            <div class="label">Изучено слов</div>
                        </div>
                        <div class="stat-item">
                            <div class="number">${stats.mastered_words}</div>
                            <div class="label">Освоено</div>
                        </div>
                        <div class="stat-item">
                            <div class="number">${stats.tests_completed}</div>
                            <div class="label">Тестов пройдено</div>
                        </div>
                        <div class="stat-item">
                            <div class="number">${Math.round(stats.accuracy || 0)}%</div>
                            <div class="label">Точность</div>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${stats.words_percentage || 0}%">
                            ${Math.round(stats.words_percentage || 0)}%
                        </div>
                    </div>
                `;
            } catch (error) {
                document.getElementById('progress-stats').innerHTML = 
                    '<div class="error">Ошибка загрузки статистики</div>';
            }
        }
        
        // Initialize
        window.onload = function() {
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
    
    asyncio.run(update_word_progress(user_id, data['word_id'], data['is_correct']))
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
