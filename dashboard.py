import os
import secrets
from flask import Flask, render_template_string, request, redirect, url_for, session
from functools import wraps
from database import init_database, get_all_users, get_user_chat_history, get_dashboard_stats

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET') or secrets.token_hex(32)

ADMIN_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')

if not ADMIN_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD environment variable must be set")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Keerthana Bot - Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #ff6b9d; margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-value { font-size: 2.5em; color: #ff6b9d; font-weight: bold; }
        .stat-label { color: #888; margin-top: 5px; }
        .users-table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 10px; overflow: hidden; }
        .users-table th, .users-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #2a2a4e; }
        .users-table th { background: #0f3460; color: #ff6b9d; }
        .users-table tr:hover { background: #1f4068; cursor: pointer; }
        .btn { background: #ff6b9d; color: white; padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn:hover { background: #e91e63; }
        .logout { position: absolute; top: 20px; right: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💕 Keerthana Bot Dashboard</h1>
            <a href="/logout" class="btn">Logout</a>
        </div>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_users }}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_messages }}</div>
                <div class="stat-label">Total Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.active_today }}</div>
                <div class="stat-label">Active Today</div>
            </div>
        </div>
        <h2 style="margin-bottom: 15px;">Users</h2>
        <table class="users-table">
            <thead>
                <tr>
                    <th>User</th>
                    <th>Username</th>
                    <th>Messages</th>
                    <th>Daily Used</th>
                    <th>Bonus</th>
                    <th>Referrals</th>
                    <th>Last Active</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for user in users %}
                <tr>
                    <td>{{ user.preferred_name or user.first_name or 'Unknown' }}</td>
                    <td>@{{ user.username or 'N/A' }}</td>
                    <td>{{ user.message_count }}</td>
                    <td>{{ user.daily_messages_used }}/20</td>
                    <td>{{ user.bonus_messages }}</td>
                    <td>{{ user.referral_count }}</td>
                    <td>{{ user.last_active.strftime('%Y-%m-%d %H:%M') if user.last_active else 'Never' }}</td>
                    <td><a href="/chat/{{ user.user_id }}" class="btn">View Chat</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
'''

CHAT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Chat History - {{ user_name }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #ff6b9d; margin-bottom: 20px; }
        .back-btn { margin-bottom: 20px; }
        .btn { background: #ff6b9d; color: white; padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn:hover { background: #e91e63; }
        .chat-container { background: #16213e; border-radius: 10px; padding: 20px; max-height: 70vh; overflow-y: auto; }
        .message { margin-bottom: 15px; padding: 10px 15px; border-radius: 10px; max-width: 80%; }
        .message.user { background: #0f3460; margin-left: auto; }
        .message.assistant { background: #2a2a4e; margin-right: auto; }
        .message-role { font-size: 0.8em; color: #ff6b9d; margin-bottom: 5px; }
        .message-time { font-size: 0.7em; color: #666; margin-top: 5px; }
        .message-content { word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="container">
        <div class="back-btn">
            <a href="/" class="btn">← Back to Dashboard</a>
        </div>
        <h1>Chat: {{ user_name }}</h1>
        <p style="color: #888; margin-bottom: 20px;">User ID: {{ user_id }}</p>
        <div class="chat-container">
            {% for msg in messages %}
            <div class="message {{ msg.role }}">
                <div class="message-role">{{ 'User' if msg.role == 'user' else 'Keerthana' }}</div>
                <div class="message-content">{{ msg.content }}</div>
                <div class="message-time">{{ msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else '' }}</div>
            </div>
            {% endfor %}
            {% if not messages %}
            <p style="text-align: center; color: #666;">No messages yet</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-box { background: #16213e; padding: 40px; border-radius: 10px; width: 100%; max-width: 400px; }
        h1 { color: #ff6b9d; margin-bottom: 30px; text-align: center; }
        input { width: 100%; padding: 12px; margin-bottom: 20px; border: none; border-radius: 5px; background: #0f3460; color: #fff; }
        button { width: 100%; padding: 12px; background: #ff6b9d; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #e91e63; }
        .error { color: #ff4444; text-align: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>💕 Keerthana Dashboard</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" required>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid password'
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    users = get_all_users()
    stats = get_dashboard_stats()
    return render_template_string(DASHBOARD_HTML, users=users, stats=stats)

@app.route('/chat/<int:user_id>')
@login_required
def view_chat(user_id):
    messages = get_user_chat_history(user_id, limit=200)
    users = get_all_users()
    user = next((u for u in users if u['user_id'] == user_id), None)
    user_name = user['preferred_name'] or user['first_name'] if user else 'Unknown'
    return render_template_string(CHAT_HTML, messages=messages, user_id=user_id, user_name=user_name)

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=False)
