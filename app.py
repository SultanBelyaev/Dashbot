from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import time

app = Flask(__name__)

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatbot_logs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db = SQLAlchemy(app)

# Модель для хранения логов взаимодействий
class InteractionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    query_text = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50), nullable=True)  # Распознанное намерение
    resolved = db.Column(db.Boolean, default=True)  # Был ли запрос решен ботом
    rating = db.Column(db.Integer, nullable=True)  # Оценка пользователя (1-5)
    response_time = db.Column(db.Float, nullable=True)  # Время ответа в секундах
    channel = db.Column(db.String(50), default='web')  # Канал (web, telegram, etc.)
    language = db.Column(db.String(10), default='ru')  # Язык запроса
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'query_text': self.query_text,
            'bot_response': self.bot_response,
            'intent': self.intent,
            'resolved': self.resolved,
            'rating': self.rating,
            'response_time': self.response_time,
            'channel': self.channel,
            'language': self.language
        }

def generate_bot_reply(user_text):
    """
    Функция для генерации ответа чат-бота на основе пользовательского ввода
    Возвращает кортеж: (ответ, намерение, решен_ли_запрос)
    """
    import time
    
    text = user_text.lower()
    
    # Приветствие
    if any(greet in text for greet in ["привет", "здравствуй", "hello", "hi", "добрый день", "добрый вечер", "доброе утро"]):
        time.sleep(0.1)  # Небольшая задержка
        return "Здравствуйте! Чем могу помочь?", "greeting", True
    
    # Время
    elif "время" in text or "который час" in text:
        time.sleep(0.2)  # Чуть больше времени для "сложного" запроса
        now = datetime.now().strftime("%H:%M")
        return f"Сейчас {now}.", "time_query", True
    
    # Дата
    elif "дата" in text or "какое число" in text or "какой день" in text or "число" in text:
        time.sleep(0.2)  # Чуть больше времени для "сложного" запроса
        now = datetime.now().strftime("%d.%m.%Y")
        return f"Сегодня {now}.", "date_query", True
    
    # Погода
    elif "погода" in text or "дождь" in text or "солнце" in text:
        time.sleep(0.3)  # Больше времени для "сложного" анализа
        return "К сожалению, я не могу проверить погоду. Рекомендую посмотреть в приложении погоды.", "weather_query", False
    
    # Помощь
    elif any(help_word in text for help_word in ["помощь", "help", "что ты умеешь", "функции"]):
        time.sleep(0.15)  # Средняя задержка
        return "Я умею отвечать на приветствия, говорить время и дату, а также отвечать на простые вопросы. Попробуйте спросить что-то простое!", "help_request", True
    
    # Благодарность
    elif any(thanks in text for thanks in ["спасибо", "благодарю", "thanks", "thank you"]):
        time.sleep(0.1)  # Небольшая задержка
        return "Пожалуйста! Рад был помочь!", "thanks", True
    
    # Прощание
    elif any(bye in text for bye in ["пока", "до свидания", "bye", "goodbye", "увидимся"]):
        time.sleep(0.1)  # Небольшая задержка
        return "До свидания! Хорошего дня!", "goodbye", True
    
    # Вопросы о боте
    elif any(bot_word in text for bot_word in ["кто ты", "что ты", "как тебя зовут", "имя"]):
        time.sleep(0.15)  # Средняя задержка
        return "Я простой чат-бот, созданный для демонстрации. Меня зовут Бот!", "bot_info", True
    
    # Вопросы о возрасте
    elif "возраст" in text or "сколько тебе" in text:
        time.sleep(0.15)  # Средняя задержка
        return "Я только что родился в этом коде! 😊", "bot_info", True
    
    # По умолчанию
    else:
        time.sleep(0.3)  # Больше времени для "сложного" анализа
        return "Извините, я не понял вопрос. Попробуйте сформулировать по-другому или спросите о времени, дате или просто поздоровайтесь!", "unknown", False

# Маршрут для главной страницы
@app.route("/")
def home():
    return render_template('index.html')


# Основной маршрут для общения
@app.route("/chat", methods=["POST"])
def chat():
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Отсутствует поле 'message' в запросе"}), 400
        
        user_input = data['message']
        if not user_input.strip():
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        
        # Получаем user_id и session_id из запроса или генерируем
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id', str(uuid.uuid4()))
        channel = data.get('channel', 'web')
        language = data.get('language', 'ru')
        
        # Генерируем ответ бота с метаданными
        bot_reply, intent, resolved = generate_bot_reply(user_input)
        
        # Вычисляем время ответа (время обработки запроса)
        response_time = time.time() - start_time
        
        # Создаем запись в логе
        log_entry = InteractionLog(
            user_id=user_id,
            session_id=session_id,
            query_text=user_input,
            bot_response=bot_reply,
            intent=intent,
            resolved=resolved,
            response_time=response_time,
            channel=channel,
            language=language
        )
        
        # Сохраняем в базу данных
        db.session.add(log_entry)
        db.session.commit()
        
        # Возвращаем ответ с ID записи для возможной оценки
        return jsonify({
            "response": bot_reply,
            "log_id": log_entry.id,
            "intent": intent,
            "resolved": resolved
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500

# Маршрут для оценки ответов
@app.route("/rate", methods=["POST"])
def rate_response():
    try:
        data = request.get_json()
        if not data or 'log_id' not in data or 'rating' not in data:
            return jsonify({"error": "Отсутствуют поля 'log_id' или 'rating'"}), 400
        
        log_id = data['log_id']
        rating = data['rating']
        
        # Проверяем, что оценка в допустимом диапазоне
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Оценка должна быть числом от 1 до 5"}), 400
        
        # Находим запись в логе
        log_entry = db.session.get(InteractionLog, log_id)
        if not log_entry:
            return jsonify({"error": "Запись не найдена"}), 404
        
        # Обновляем оценку
        log_entry.rating = rating
        db.session.commit()
        
        return jsonify({"message": "Оценка сохранена", "log_id": log_id, "rating": rating})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500

# Маршрут для получения статистики
@app.route("/stats")
def get_stats():
    try:
        # Общее количество взаимодействий
        total_interactions = InteractionLog.query.count()
        
        # Количество оцененных ответов
        rated_interactions = InteractionLog.query.filter(InteractionLog.rating.isnot(None)).count()
        
        # Средняя оценка
        avg_rating = db.session.query(db.func.avg(InteractionLog.rating)).filter(
            InteractionLog.rating.isnot(None)
        ).scalar() or 0
        
        # Количество решенных запросов
        resolved_count = InteractionLog.query.filter(InteractionLog.resolved == True).count()
        
        # Распределение по намерениям
        intent_stats = db.session.query(
            InteractionLog.intent,
            db.func.count(InteractionLog.id)
        ).group_by(InteractionLog.intent).all()
        
        # Среднее время ответа
        avg_response_time = db.session.query(db.func.avg(InteractionLog.response_time)).scalar() or 0
        
        return jsonify({
            "total_interactions": total_interactions,
            "rated_interactions": rated_interactions,
            "average_rating": round(avg_rating, 2),
            "resolved_count": resolved_count,
            "resolution_rate": round((resolved_count / total_interactions * 100) if total_interactions > 0 else 0, 2),
            "average_response_time": round(avg_response_time, 3),
            "intent_distribution": dict(intent_stats)
        })
    
    except Exception as e:
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500

# Маршрут для получения логов (для администрирования)
@app.route("/logs")
def get_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        user_id = request.args.get('user_id')
        
        query = InteractionLog.query
        
        if user_id:
            query = query.filter(InteractionLog.user_id == user_id)
        
        logs = query.order_by(InteractionLog.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            "logs": [log.to_dict() for log in logs.items],
            "total": logs.total,
            "pages": logs.pages,
            "current_page": page,
            "per_page": per_page
        })
    
    except Exception as e:
        return jsonify({"error": f"Ошибка сервера: {str(e)}"}), 500

# Маршрут для получения статуса (опционально)
@app.route("/status")
def status():
    return jsonify({
        "status": "online",
        "bot_name": "Simple ChatBot",
        "version": "2.0",
        "features": ["greeting", "time", "date", "basic_qa", "logging", "rating"]
    })


# Инициализация базы данных
def init_db():
    """Создание таблиц базы данных"""
    with app.app_context():
        db.create_all()
        print("✅ База данных инициализирована")

if __name__ == "__main__":
    # Инициализируем базу данных при запуске
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
