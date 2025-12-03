from flask import Flask, request, jsonify, render_template_string, Response, redirect, url_for
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

app = Flask(__name__)
notifications_file = 'notifications.json'
sessions_file = 'sessions.json'
notifications = []
sessions = []

# Загрузи существующие уведомления при старте
if os.path.exists(notifications_file):
    with open(notifications_file, 'r', encoding='utf-8') as f:
        notifications = json.load(f)

# Загрузи существующие сессии при старте
if os.path.exists(sessions_file):
    with open(sessions_file, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

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
def index():
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
    
    # Создаем новую сессию при входе
    session_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_session = {
        'id': len(sessions),
        'start_time': session_start_time,
        'notification_count': len(notifications)
    }
    sessions.append(new_session)
    
    # Сохраняем сессию в файл
    with open(sessions_file, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)
    
    # HTML-меню с выбором между текущей и предыдущими сессиями
    html = """
    <h1>Меню сессий</h1>
    <button onclick="window.location.href='/current_session'">Текущая сессия</button>
    <button onclick="window.location.href='/previous_sessions'">Смотреть предыдущие</button>
    """
    return render_template_string(html)

@app.route('/current_session', methods=['GET'])
def current_session():
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
    <h1>Текущая сессия</h1>
    <button onclick="window.location.href='/'">Назад</button>
    <ul>
    {% for notif in notifications %}
    <li>
        <strong>Группа:</strong> {{ notif.group }}<br>
        <strong>Отправитель:</strong> {{ notif.sender }} (ID: {{ notif.user_id }})<br>
        <strong>Текст:</strong> {{ notif.text }}<br>
        <strong>Анализ ИИ:</strong> {{ notif.ai }}<br>
        <strong>Время:</strong> {{ notif.received_at }}<br>
        {% if notif.chat_id and notif.message_id %}
          <a href="https://t.me/c/{{ (notif.chat_id|string)[4:] }}/{{ notif.message_id }}" target="_blank" style="font-weight:bold; color:#0088cc;">
            Открыть сообщение в группе
          </a>
        {% else %}
          <em style="color:#888;">(ссылка на сообщение недоступна)</em>
        {% endif %}
        &nbsp;|&nbsp;
        <a href="tg://user?id={{ notif.user_id }}" style="color:#00aa00;">
          Написать в ЛС (мобилка/десктоп)
        </a>
        &nbsp;|&nbsp;
        <a href="https://t.me/{{ notif.user_id }}" target="_blank" style="color:#666;">
          Профиль в вебе
        </a>
        <hr>
    </li>
    {% endfor %}
    </ul>
    <p>Всего уведомлений: {{ notifications|length }}</p>
    """
    return render_template_string(html, notifications=notifications[::-1])  # Новые сверху

@app.route('/previous_sessions', methods=['GET'])
def previous_sessions():
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
    
    # HTML-список предыдущих сессий
    html = """
    <h1>Предыдущие сессии</h1>
    <button onclick="window.location.href='/'">Назад</button>
    <ul>
    {% for session in sessions %}
    <li>
        <strong>Сессия от:</strong> {{ session.start_time }}<br>
        <strong>Количество уведомлений:</strong> {{ session.notification_count }}<br>
        <button onclick="window.location.href='/session/{{ session.id }}'">Открыть сессию</button>
        <hr>
    </li>
    {% endfor %}
    </ul>
    """
    # Исключаем последнюю сессию (она считается текущей)
    previous_sessions_list = sessions[:-1] if len(sessions) > 0 else []
    return render_template_string(html, sessions=previous_sessions_list[::-1])  # Новые сверху

@app.route('/session/<int:session_id>', methods=['GET'])
def view_session(session_id):
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
    
    # Проверяем, что сессия существует
    if session_id >= len(sessions):
        return "Сессия не найдена", 404
    
    # Получаем сессию
    session = sessions[session_id]
    
    # HTML-дашборд с информацией о сессии
    html = """
    <h1>Сессия от {{ session.start_time }}</h1>
    <button onclick="window.location.href='/previous_sessions'">Назад</button>
    <p><strong>Количество уведомлений в момент сессии:</strong> {{ session.notification_count }}</p>
    <h2>Уведомления на момент сессии:</h2>
    <ul>
    {% for notif in notifications[:session.notification_count] %}
    <li>
        <strong>Группа:</strong> {{ notif.group }}<br>
        <strong>Отправитель:</strong> {{ notif.sender }} (ID: {{ notif.user_id }})<br>
        <strong>Текст:</strong> {{ notif.text }}<br>
        <strong>Анализ ИИ:</strong> {{ notif.ai }}<br>
        <strong>Время:</strong> {{ notif.received_at }}<br>
        {% if notif.chat_id and notif.message_id %}
          <a href="https://t.me/c/{{ (notif.chat_id|string)[4:] }}/{{ notif.message_id }}" target="_blank" style="font-weight:bold; color:#0088cc;">
            Открыть сообщение в группе
          </a>
        {% else %}
          <em style="color:#888;">(ссылка на сообщение недоступна)</em>
        {% endif %}
        &nbsp;|&nbsp;
        <a href="tg://user?id={{ notif.user_id }}" style="color:#00aa00;">
          Написать в ЛС (мобилка/десктоп)
        </a>
        &nbsp;|&nbsp;
        <a href="https://t.me/{{ notif.user_id }}" target="_blank" style="color:#666;">
          Профиль в вебе
        </a>
        <hr>
    </li>
    {% endfor %}
    </ul>
    """
    return render_template_string(html, session=session, notifications=notifications)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)