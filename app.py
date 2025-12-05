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

# Храним все уведомления в памяти вместо файлов
notifications = []
clients = []  # Для Server-Sent Events

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает пакеты сообщений от бота и сохраняет их в памяти"""
    data = request.json
    if not data:
        return jsonify({'error': 'No JSON data'}), 400
    
    # Если это пакет сообщений
    if 'messages' in data:
        messages = data['messages']
        batch_sent_at = data.get('batch_sent_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Добавляем все сообщения из пакета
        for msg in messages:
            msg['received_at'] = batch_sent_at
            notifications.append(msg)
        
        print(f"Получен пакет из {len(messages)} сообщений")
        return jsonify({'status': 'ok', 'count': len(messages)})
    else:
        # Одиночное сообщение (для совместимости)
        data['received_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        notifications.append(data)
        print("Получено одиночное сообщение")
        return jsonify({'status': 'ok'})

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
        client_id = len(clients)
        clients.append(True)  # Добавляем клиента в список
        last_count = 0
        
        try:
            while clients[client_id]:  # Пока клиент активен
                try:
                    # Отправляем уведомления только если их количество изменилось
                    if len(notifications) != last_count:
                        yield f"data: {json.dumps(notifications, ensure_ascii=False)}\n\n"
                        last_count = len(notifications)
                    
                    # Ждем 1 секунду перед следующей проверкой
                    time.sleep(1)
                except Exception as e:
                    print(f"Error in event stream: {e}")
                    yield f"data: []\n\n"
                    time.sleep(5)
        finally:
            # Удаляем клиента из списка при отключении
            if client_id < len(clients):
                clients[client_id] = False
    
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
    
    # Так как теперь всё хранится в памяти, показываем только сегодняшние уведомления
    # Но для совместимости создаем список с одной датой
    today_date = datetime.now().strftime('%Y-%m-%d')
    log_dates = [today_date]
    
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
    
    # Для совместимости показываем все уведомления (так как теперь всё в памяти)
    day_notifications = notifications
    
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