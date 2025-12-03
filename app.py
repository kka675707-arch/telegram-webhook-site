from flask import Flask, request, jsonify, render_template_string, Response
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

app = Flask(__name__)
notifications_file = 'notifications.json'
notifications = []

# Загрузи существующие уведомления при старте
if os.path.exists(notifications_file):
    with open(notifications_file, 'r', encoding='utf-8') as f:
        notifications = json.load(f)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({'error': 'No JSON data'}), 400
    data['received_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    notifications.append(data)
    # Сохрани в файл (для перезапуска)
    with open(notifications_file, 'w', encoding='utf-8') as f:
        json.dump(notifications, f, ensure_ascii=False, indent=2)
    return jsonify({'status': 'ok', 'id': len(notifications) - 1})

@app.route('/', methods=['GET'])
def dashboard():
    # Берём логин/пароль из env
    auth = request.authorization
    env_user = os.getenv("DASHBOARD_USER")
    env_pass = os.getenv("DASHBOARD_PASS")

    # Если авторизация не прошла — возвращаем 401 с заголовком WWW-Authenticate
    if not auth or auth.username != env_user or auth.password != env_pass:
        return Response(
            'Unauthorized', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )
    
    # HTML-дашборд с списком уведомлений
    html = """
    <h1>Релевантные сообщения из Telegram</h1>
    <ul>
    {% for notif in notifications %}
    <li>
        <strong>Группа:</strong> {{ notif.group }}<br>
        <strong>Отправитель:</strong> {{ notif.sender }} (ID: {{ notif.user_id }})<br>
        <strong>Текст:</strong> {{ notif.text }}<br>
        <strong>Анализ ИИ:</strong> {{ notif.ai }}<br>
        <strong>Время:</strong> {{ notif.received_at }}<br>
        <a href="tg://user?id={{ notif.user_id }}">Написать в ЛС</a> | <a href="https://t.me/{{ notif.user_id }}">Открыть профиль</a>
        <hr>
    </li>
    {% endfor %}
    </ul>
    <p>Всего уведомлений: {{ notifications|length }}</p>
    """
    return render_template_string(html, notifications=notifications[::-1])  # Новые сверху

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
