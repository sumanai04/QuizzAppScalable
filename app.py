from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
import redis
import json
import uuid
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'

# Configuration for Redis
redis_client = redis.StrictRedis(
    host=os.getenv('REDIS_HOST', 'decent-mammoth-33852.upstash.io'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', 'AYQ8AAIncDFjZjY5ODU2NzU0YzI0M2UxODQ3NWM4ZDQ4ZTJhYmY5N3AxMzM4NTI'),
    ssl=bool(os.getenv('REDIS_SSL', True)),
    decode_responses=False  # Disable automatic decoding to handle non-UTF-8 data
)
app.config['SESSION_REDIS'] = redis_client

Session(app)

def decode_redis_data(data):
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    quizzes = []
    for key in redis_client.scan_iter("quiz:*"):
        quiz = redis_client.get(key)
        if quiz:
            quiz = json.loads(decode_redis_data(quiz))
            quizzes.append(quiz)
    return render_template('index.html', quizzes=quizzes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        get_user = redis_client.get(f'user:{username}')
        if get_user:
            get_user = json.loads(decode_redis_data(get_user))
            get_user_id = get_user['id']
            user_data = redis_client.get(f'user:{get_user_id}')
            if user_data:
                user = json.loads(decode_redis_data(user_data))
                if user['password'] == password:
                    session['user_id'] = user['id']
                    return redirect(url_for('index'))
        error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = str(uuid.uuid4())
        user_data = {'id': user_id, 'username': username, 'password': password}
        redis_client.set(f'user:{user_id}', json.dumps(user_data).encode('utf-8'))
        username_data = {'id': user_id}
        redis_client.set(f'user:{username}', json.dumps(username_data).encode('utf-8'))
        session['user_id'] = user_id
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if request.method == 'POST':
        quiz_name = request.form['quiz_name']
        questions = request.form.getlist('question')
        options1 = request.form.getlist('option1')
        options2 = request.form.getlist('option2')
        options3 = request.form.getlist('option3')
        options4 = request.form.getlist('option4')
        correct_options = request.form.getlist('correct_option')

        quiz_id = str(uuid.uuid4())
        quiz_data = {'id': quiz_id, 'name': quiz_name, 'questions': []}
        for i in range(len(questions)):
            question_data = {
                'id': str(uuid.uuid4()),
                'question': questions[i],
                'options': [options1[i], options2[i], options3[i], options4[i]],
                'correct_option': correct_options[i]
            }
            quiz_data['questions'].append(question_data)

        redis_client.set(f'quiz:{quiz_id}', json.dumps(quiz_data).encode('utf-8'))
        return redirect(url_for('index')) 
    return render_template('create_quiz.html')

@app.route('/quiz/<quiz_id>')
@login_required
def quiz(quiz_id):
    quiz_data = redis_client.get(f'quiz:{quiz_id}')
    if quiz_data:
        quiz_data = json.loads(decode_redis_data(quiz_data))
        return render_template('quiz.html', quiz=quiz_data)
    else:
        return "Quiz not found", 404

@app.route('/submit/<quiz_id>', methods=['POST'])
@login_required
def submit(quiz_id):
    answers = request.form.to_dict()
    quiz_data = redis_client.get(f'quiz:{quiz_id}')
    if not quiz_data:
        return "Quiz not found", 404

    quiz_data = json.loads(decode_redis_data(quiz_data))
    questions = quiz_data['questions']
    score = 0
    for question in questions:
        question_id = question['id']
        correct_option = question['correct_option']
        if str(correct_option) == answers.get(str(question_id)):
            score += 1

    user_id = session['user_id']
    leaderboard_key = f'leaderboard:{quiz_id}'
    leaderboard_entry = {'user_id': user_id, 'score': score}
    redis_client.lpush(leaderboard_key, json.dumps(leaderboard_entry).encode('utf-8'))

    return render_template('result.html', score=score, total=len(questions), quiz_id=quiz_id)

@app.route('/leaderboard/<quiz_id>')
@login_required
def leaderboard(quiz_id):
    leaderboard_key = f'leaderboard:{quiz_id}'
    leaderboard_data = redis_client.lrange(leaderboard_key, 0, -1)
    if not leaderboard_data:
        return "No leaderboard data found", 404

    leaderboard_entries = [json.loads(decode_redis_data(entry)) for entry in leaderboard_data]
    leaderboard_entries.sort(key=lambda x: x['score'], reverse=True)

    users = []
    for entry in leaderboard_entries:
        user_id = entry.get('user_id')
        if user_id:
            user_key = f'user:{user_id}'
            user_data = redis_client.get(user_key)
            if user_data:
                user_data = json.loads(decode_redis_data(user_data))
                username = user_data.get('username')
                score = entry['score']
                users.append({'username': username, 'score': score})
        else:
            users.append({'username': 'Unknown', 'score': entry['score']})

    return render_template('leaderboard.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)
