from flask import Flask, request, jsonify, render_template_string, Response, redirect, url_for
import json
from datetime import datetime
import os
import glob
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

app = Flask(__name__)
notifications_file = 'notifications.json'
daily_logs_dir = 'daily_logs'  # Путь к директории с дневными логами относительно текущей директории

# Загрузи существующие уведомления при старте
if os.path.exists(notifications_file):
    with open(notifications_file, 'r', encoding='utf-8') as f:
        notifications = json.load(f)
else:
    notifications = []

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
    
    # HTML-меню с выбором между текущей датой и предыдущими днями
    html = """
    <h1>Меню логов</h1>
    <button onclick="window.location.href='/today'">Сегодня</button>
    <button onclick="window.location.href='/previous_days'">Предыдущие дни</button>
    """
    return render_template_string(html)

@app.route('/today', methods=['GET'])
def today():
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
    
    # Получаем сегодняшнюю дату
    today_date = datetime.now().strftime('%Y-%m-%d')
    log_file = f"{daily_logs_dir}/{today_date}.json"
    
    # Загружаем данные за сегодня
    today_notifications = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                today_notifications = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения файла {log_file}: {e}")
    
    # HTML-дашборд с автообновлением каждые 30 секунд
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Текущие уведомления</title>
        <script>
            // Автообновление страницы каждые 30 секунд
            setTimeout(function(){
                window.location.reload();
            }, 30000);
        </script>
    </head>
    <body>
        <h1>Уведомления за сегодня (""" + today_date + """)</h1>
        <p><em>Страница автоматически обновляется каждые 30 секунд</em></p>
        <button onclick="window.location.href='/'">Назад</button>
        <ul>
        {% for notif in notifications %}
        <li>
            <strong>Группа:</strong> {{ notif.group }}<br>
            <strong>Отправитель:</strong> {{ notif.sender }}{% if notif.sender_username %} (@{{ notif.sender_username }}){% endif %} (ID: {{ notif.user_id }})<br>
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
    </body>
    </html>
    """
    return render_template_string(html, notifications=today_notifications[::-1])  # Новые сверху

@app.route('/previous_days', methods=['GET'])
def previous_days():
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
    
    # Получаем список файлов логов
    log_files = glob.glob(f"{daily_logs_dir}/*.json")
    log_dates = []
    
    for log_file in log_files:
        filename = os.path.basename(log_file)
        date_str = filename.replace('.json', '')
        try:
            # Проверяем, что имя файла соответствует формату даты
            datetime.strptime(date_str, '%Y-%m-%d')
            log_dates.append(date_str)
        except ValueError:
            pass  # Пропускаем файлы с неправильным форматом имени
    
    # Сортируем даты по убыванию
    log_dates.sort(reverse=True)
    
    # HTML-список предыдущих дней
    html = """
    <h1>Предыдущие дни</h1>
    <button onclick="window.location.href='/'">Назад</button>
    <ul>
    {% for date in dates %}
    <li>
        <strong>Лог за:</strong> {{ date }}<br>
        <button onclick="window.location.href='/day/{{ date }}'">Открыть лог</button>
        <hr>
    </li>
    {% endfor %}
    </ul>
    """
    return render_template_string(html, dates=log_dates)

@app.route('/day/<date_str>', methods=['GET'])
def view_day(date_str):
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
    
    # Проверяем, что дата имеет правильный формат
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return "Неправильный формат даты", 400
    
    # Загружаем данные за указанный день
    log_file = f"{daily_logs_dir}/{date_str}.json"
    day_notifications = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                day_notifications = json.load(f)
        except Exception as e:
            return f"Ошибка чтения файла: {e}", 500
    
    # HTML-дашборд с информацией за день
    html = """
    <h1>Лог за {{ date }}</h1>
    <button onclick="window.location.href='/previous_days'">Назад</button>
    <ul>
    {% for notif in notifications %}
    <li>
        <strong>Группа:</strong> {{ notif.group }}<br>
        <strong>Отправитель:</strong> {{ notif.sender }}{% if notif.sender_username %} (@{{ notif.sender_username }}){% endif %} (ID: {{ notif.user_id }})<br>
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
    return render_template_string(html, date=date_str, notifications=day_notifications[::-1])  # Новые сверху

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)