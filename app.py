from flask import Flask, request, jsonify, render_template_string, Response, redirect, url_for, stream_with_context
import json
from datetime import datetime
import os
import glob
import time
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

def get_today_notifications():
    """Получает уведомления за сегодня"""
    today_date = datetime.now().strftime('%Y-%m-%d')
    log_file = f"{daily_logs_dir}/{today_date}.json"
    
    today_notifications = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                today_notifications = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения файла {log_file}: {e}")
    
    return today_notifications

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
    
    # HTML-дашборд с SSE для реального времени
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Текущие уведомления</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .notification { border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }
            .notification strong { color: #333; }
            .notification hr { margin: 10px 0; }
            .time { color: #666; font-size: 0.9em; }
            .sender { color: #0066cc; }
            .group { color: #cc6600; }
            .ai-result { color: #009900; }
            .links a { margin-right: 10px; text-decoration: none; }
            .links a:hover { text-decoration: underline; }
            #notifications { margin-top: 20px; }
            button { padding: 10px 15px; margin: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Уведомления за сегодня (""" + today_date + """)</h1>
        <p><em>Дашборд обновляется в реальном времени</em></p>
        <button onclick="window.location.href='/'">Назад</button>
        <div id="notifications"></div>

        <script>
            const eventSource = new EventSource('/stream');
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const container = document.getElementById('notifications');
                
                // Очищаем контейнер и добавляем уведомления в обратном порядке (новые сверху)
                container.innerHTML = '';
                
                // Добавляем уведомления в обратном порядке (новые сверху)
                for (let i = data.length - 1; i >= 0; i--) {
                    const notif = data[i];
                    
                    const notifDiv = document.createElement('div');
                    notifDiv.className = 'notification';
                    
                    let senderText = notif.sender;
                    if (notif.sender_username) {
                        senderText += ' (@' + notif.sender_username + ')';
                    }
                    senderText += ' (ID: ' + notif.user_id + ')';
                    
                    let messageLink = '';
                    if (notif.chat_id && notif.message_id) {
                        const chatIdStripped = notif.chat_id.toString().substring(4);
                        messageLink = '<a href="https://t.me/c/' + chatIdStripped + '/' + notif.message_id + '" target="_blank" style="font-weight:bold; color:#0088cc;">Открыть сообщение в группе</a>';
                    } else {
                        messageLink = '<em style="color:#888;">(ссылка на сообщение недоступна)</em>';
                    }
                    
                    const profileLink = '<a href="tg://user?id=' + notif.user_id + '" style="color:#00aa00;">Написать в ЛС (мобилка/десктоп)</a>';
                    const webProfileLink = '<a href="https://t.me/' + notif.user_id + '" target="_blank" style="color:#666;">Профиль в вебе</a>';
                    
                    notifDiv.innerHTML = 
                        '<strong>Группа:</strong> <span class="group">' + notif.group + '</span><br>' +
                        '<strong>Отправитель:</strong> <span class="sender">' + senderText + '</span><br>' +
                        '<strong>Текст:</strong> ' + notif.text + '<br>' +
                        '<strong>Анализ ИИ:</strong> <span class="ai-result">' + notif.ai + '</span><br>' +
                        '<strong>Время:</strong> <span class="time">' + notif.received_at + '</span><br>' +
                        '<div class="links">' + messageLink + ' | ' + profileLink + ' | ' + webProfileLink + '</div>' +
                        '<hr>';
                    
                    container.appendChild(notifDiv);
                }
                
                // Обновляем счетчик уведомлений
                const countParagraph = document.createElement('p');
                countParagraph.innerHTML = '<strong>Всего уведомлений:</strong> ' + data.length;
                container.appendChild(countParagraph);
            };
            
            eventSource.onerror = function(event) {
                console.error('SSE error:', event);
            };
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/stream')
def stream():
    """Server-Sent Events endpoint for real-time updates"""
    auth = request.authorization
    env_user = os.getenv("DASHBOARD_USER")
    env_pass = os.getenv("DASHBOARD_PASS")

    # Если авторизация не прошла — возвращаем 401 с заголовком WWW-Authenticate
    if not auth or auth.username != env_user or auth.password != env_pass:
        return Response(
            'Unauthorized', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )
    
    def event_stream():
        prev_notifications = []
        while True:
            try:
                current_notifications = get_today_notifications()
                
                # Проверяем, изменились ли уведомления
                if current_notifications != prev_notifications:
                    # Отправляем обновленный список уведомлений
                    yield f"data: {json.dumps(current_notifications, ensure_ascii=False)}\n\n"
                    prev_notifications = current_notifications
                
                # Ждем 1 секунду перед следующей проверкой
                time.sleep(1)
            except Exception as e:
                print(f"Error in event stream: {e}")
                yield f"data: []\n\n"
                time.sleep(5)
    
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

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
    
    # HTML-дашборд с информацией за день (статический, без SSE)
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Лог за """ + date_str + """</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .notification { border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }
            .notification strong { color: #333; }
            .notification hr { margin: 10px 0; }
            .time { color: #666; font-size: 0.9em; }
            .sender { color: #0066cc; }
            .group { color: #cc6600; }
            .ai-result { color: #009900; }
            .links a { margin-right: 10px; text-decoration: none; }
            .links a:hover { text-decoration: underline; }
            #notifications { margin-top: 20px; }
            button { padding: 10px 15px; margin: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Лог за """ + date_str + """</h1>
        <button onclick="window.location.href='/previous_days'">Назад</button>
        <div id="notifications">
    """
    
    # Добавляем уведомления в обратном порядке (новые сверху)
    for notif in reversed(day_notifications):
        sender_text = notif['sender']
        if 'sender_username' in notif and notif['sender_username']:
            sender_text += ' (@' + notif['sender_username'] + ')'
        sender_text += ' (ID: ' + str(notif['user_id']) + ')'
        
        message_link = ''
        if 'chat_id' in notif and 'message_id' in notif and notif['chat_id'] and notif['message_id']:
            chat_id_stripped = str(notif['chat_id'])[4:] if str(notif['chat_id']).startswith('-100') else notif['chat_id']
            message_link = f'<a href="https://t.me/c/{chat_id_stripped}/{notif["message_id"]}" target="_blank" style="font-weight:bold; color:#0088cc;">Открыть сообщение в группе</a>'
        else:
            message_link = '<em style="color:#888;">(ссылка на сообщение недоступна)</em>'
        
        profile_link = f'<a href="tg://user?id={notif["user_id"]}" style="color:#00aa00;">Написать в ЛС (мобилка/десктоп)</a>'
        web_profile_link = f'<a href="https://t.me/{notif["user_id"]}" target="_blank" style="color:#666;">Профиль в вебе</a>'
        
        html += f'''
        <div class="notification">
            <strong>Группа:</strong> <span class="group">{notif['group']}</span><br>
            <strong>Отправитель:</strong> <span class="sender">{sender_text}</span><br>
            <strong>Текст:</strong> {notif['text']}<br>
            <strong>Анализ ИИ:</strong> <span class="ai-result">{notif['ai']}</span><br>
            <strong>Время:</strong> <span class="time">{notif['received_at']}</span><br>
            <div class="links">{message_link} | {profile_link} | {web_profile_link}</div>
            <hr>
        </div>
        '''
    
    html += f'''
        </div>
        <p><strong>Всего уведомлений:</strong> {len(day_notifications)}</p>
    </body>
    </html>
    '''
    
    return html

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)