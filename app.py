import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, User, Lesson, LessonProgress, CodeSnippet, CodeStyle, StyleExample, Question, QuizAttempt, seed_data
from ai_engine import explain_code, compare_styles, get_ai_provider

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
# Use Postgres when DATABASE_URL is provided; otherwise fall back to a
# serverless-writable SQLite file in /tmp (Vercel's CWD is read-only).
_DB_URL = os.environ.get('DATABASE_URL')
if not _DB_URL:
    _DB_URL = 'sqlite:////tmp/codementor.db'
if _DB_URL.startswith('postgres://'):
    _DB_URL = _DB_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ---------- Auth helpers ----------

def ensure_default_admin():
    admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@codementor.local')
    if not User.query.filter_by(username=admin_user).first():
        u = User(username=admin_user, email=admin_email, role='admin')
        u.set_password(admin_pass)
        db.session.add(u)
        db.session.commit()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html', user=current_user())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'student')
        if not username or not password:
            flash('Username and password required.', 'danger')
            return redirect(url_for('register'))
        if email and User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email or None,
                    role=role if role in ('student', 'admin') else 'student')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', user=current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        # Users can log in with either their username or their email
        user = User.query.filter((User.username == identity) | (User.email == identity)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = (user.role == 'admin')
            flash('Welcome back, {}!'.format(user.username), 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email/username or password.', 'danger')
    return render_template('login.html', user=current_user())

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ---------- Password change (any logged-in user; admins too) ----------
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        user = current_user()
        if not user.check_password(current):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('change_password'))
        if len(new_pass) < 4:
            flash('New password must be at least 4 characters.', 'danger')
            return redirect(url_for('change_password'))
        if new_pass != confirm:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('change_password'))
        user.set_password(new_pass)
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('change_password.html', user=current_user())

# ---------- Lessons / Learning ----------
@app.route('/learn')
def learn():
    lessons = Lesson.query.order_by(Lesson.order).all()
    progress = {}
    if session.get('user_id'):
        for lp in LessonProgress.query.filter_by(user_id=session['user_id']).all():
            progress[lp.lesson_id] = lp.completed
    return render_template('learn.html', user=current_user(), lessons=lessons, progress=progress)

@app.route('/lesson/<int:lesson_id>')
@login_required
def lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    return render_template('lesson.html', user=current_user(), lesson=lesson)

@app.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def mark_complete(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    lp = LessonProgress.query.filter_by(user_id=session['user_id'], lesson_id=lesson_id).first()
    if not lp:
        lp = LessonProgress(user_id=session['user_id'], lesson_id=lesson_id, completed=True)
        db.session.add(lp)
    else:
        lp.completed = True
    db.session.commit()
    flash('Lesson marked complete!', 'success')
    return redirect(url_for('lesson', lesson_id=lesson_id))

# ---------- AI Features ----------
@app.route('/explain')
@login_required
def explain_page():
    return render_template('explain.html', user=current_user(), provider=get_ai_provider())

@app.route('/api/explain', methods=['POST'])
@login_required
def api_explain():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    if not code.strip():
        return jsonify({'error': 'Please paste some code first.'}), 400
    try:
        explanation = explain_code(code)
        return jsonify({'explanation': explanation})
    except Exception as e:
        return jsonify({'error': 'AI could not process this. Please try again. ({})'.format(e)}), 500

@app.route('/compare')
@login_required
def compare_page():
    snippets = CodeSnippet.query.filter_by(public=True).order_by(CodeSnippet.created_at.desc()).all()
    return render_template('compare.html', user=current_user(), snippets=snippets)

@app.route('/api/compare', methods=['POST'])
@login_required
def api_compare():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    if not code.strip():
        return jsonify({'error': 'Please paste some code first.'}), 400
    try:
        result = compare_styles(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': 'AI could not process this. Please try again. ({})'.format(e)}), 500

@app.route('/snippet', methods=['POST'])
@login_required
def save_snippet():
    code = request.form.get('code', '')
    title = request.form.get('title', 'Untitled snippet')
    if code.strip():
        s = CodeSnippet(title=title or 'Untitled', content=code, user_id=session['user_id'], public=True)
        db.session.add(s)
        db.session.commit()
        flash('Snippet saved!', 'success')
    return redirect(url_for('compare_page'))


@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    all_lessons = Lesson.query.order_by(Lesson.order).all()
    completed = LessonProgress.query.filter_by(user_id=uid, completed=True).all()
    completed_ids = {c.lesson_id for c in completed}
    completed_lessons = [l for l in all_lessons if l.id in completed_ids]
    total = len(all_lessons)
    done = len(completed_lessons)
    pct = round((done / total * 100)) if total else 0
    return render_template('dashboard.html', user=current_user(),
                           total_lessons=total, completed_count=done, pct=pct,
                           recent=completed_lessons[-5:])


# ---------- Code Playground (client-side Pyodide sandbox) ----------
@app.route('/playground')
def playground():
    return render_template('playground.html', user=current_user())

# ---------- Quiz System ----------
@app.route('/quiz/<int:lesson_id>', methods=['GET'])
@login_required
def quiz(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        flash('Lesson not found.', 'danger')
        return redirect(url_for('learn'))
    questions = Question.query.filter_by(lesson_id=lesson_id).all()
    if not questions:
        flash('No quiz questions yet for this lesson.', 'info')
        return redirect(url_for('lesson', lesson_id=lesson_id))
    best = QuizAttempt.query.filter_by(user_id=session['user_id'], lesson_id=lesson_id)\
        .order_by(QuizAttempt.score_pct.desc()).first()
    return render_template('quiz.html', user=current_user(), lesson=lesson,
                           questions=questions, best=best)

@app.route('/api/quiz/submit', methods=['POST'])
@login_required
def quiz_submit():
    data = request.get_json(silent=True) or {}
    lesson_id = data.get('lesson_id')
    answers = data.get('answers') or {}  # {question_id: chosen_index}
    questions = Question.query.filter_by(lesson_id=lesson_id).all() if lesson_id else []
    correct = 0
    detail = []
    for q in questions:
        chosen = answers.get(str(q.id))
        is_correct = (chosen is not None and int(chosen) == q.correct_index)
        if is_correct:
            correct += 1
        detail.append({'id': q.id, 'text': q.text,
                       'correct_index': q.correct_index,
                       'chosen': chosen, 'is_correct': is_correct,
                       'explanation': q.explanation})
    total = len(questions)
    pct = round((correct / total * 100)) if total else 0
    attempt = QuizAttempt(user_id=session['user_id'], lesson_id=lesson_id,
                          total=total, correct=correct, score_pct=pct)
    db.session.add(attempt)
    db.session.commit()
    return jsonify({'score': correct, 'total': total, 'pct': pct, 'detail': detail})

# ---------- Admin: Questions ----------
@app.route('/admin/questions', methods=['GET'])
@admin_required
def admin_questions():
    questions = Question.query.order_by(Question.lesson_id).all()
    lessons = Lesson.query.order_by(Lesson.order).all()
    return render_template('admin/questions.html', user=current_user(),
                           questions=questions, lessons=lessons)

@app.route('/admin/questions/add', methods=['POST'])
@admin_required
def admin_question_add():
    lesson_id = request.form.get('lesson_id') or None
    text = request.form.get('text', '').strip()
    options = request.form.get('options', '')  # one per line
    correct = request.form.get('correct_index', '0')
    explanation = request.form.get('explanation', '').strip()
    opts = [o for o in options.splitlines() if o.strip()]
    if opts and len(opts) >= 2:
        q = Question(lesson_id=int(lesson_id) if lesson_id else None, text=text,
                     options=json.dumps(opts),
                     correct_index=int(correct) if correct.isdigit() else 0,
                     explanation=explanation)
        db.session.add(q)
        db.session.commit()
        flash('Question added.', 'success')
    else:
        flash('Please provide at least 2 options.', 'danger')
    return redirect(url_for('admin_questions'))

@app.route('/admin/questions/delete/<int:qid>', methods=['POST'])
@admin_required
def admin_question_delete(qid):
    q = Question.query.get(qid)
    if q:
        db.session.delete(q)
        db.session.commit()
        flash('Question deleted.', 'success')
    return redirect(url_for('admin_questions'))

# ---------- Admin ----------
@app.route('/admin')
@login_required
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc()).all()
    lessons = Lesson.query.order_by(Lesson.order).all()
    snippets = CodeSnippet.query.order_by(CodeSnippet.created_at.desc()).all()
    return render_template('admin/admin.html', user=current_user(), users=users,
                           lessons=lessons, snippets=snippets)

@app.route('/admin/lesson/create', methods=['GET', 'POST'])
@login_required
@admin_required
def lesson_create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        category = request.form.get('category', 'basics')
        order = int(request.form.get('order', 0) or 0)
        if not title:
            flash('Title required.', 'danger')
        else:
            lesson = Lesson(title=title, content=content, category=category, order=order)
            db.session.add(lesson)
            db.session.commit()
            flash('Lesson created!', 'success')
            return redirect(url_for('admin'))
    return render_template('admin/lesson_edit.html', user=current_user(), lesson=None)

@app.route('/admin/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def lesson_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == 'POST':
        lesson.title = request.form.get('title', lesson.title).strip()
        lesson.content = request.form.get('content', lesson.content)
        lesson.category = request.form.get('category', lesson.category)
        lesson.order = int(request.form.get('order', lesson.order) or lesson.order)
        db.session.commit()
        flash('Lesson updated!', 'success')
        return redirect(url_for('admin'))
    return render_template('admin/lesson_edit.html', user=current_user(), lesson=lesson)

@app.route('/admin/lesson/<int:lesson_id>/delete', methods=['POST'])
@login_required
@admin_required
def lesson_delete(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    db.session.delete(lesson)
    db.session.commit()
    flash('Lesson deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        flash('You cannot change your own role.', 'warning')
    else:
        user.role = 'student' if user.role == 'admin' else 'admin'
        db.session.commit()
        flash('User role updated to {}.'.format(user.role), 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        flash('You cannot delete yourself.', 'warning')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'info')
    return redirect(url_for('admin'))

# Initialize schema at import time so it runs on serverless cold starts
# before the first request (essential for Postgres on Vercel).
with app.app_context():
    db.create_all()
    # Lightweight migration: add the email column if it doesn't exist yet
    # (db.create_all won't alter existing tables, e.g. old /tmp SQLite or Postgres).
    try:
        db.session.execute(db.text('ALTER TABLE users ADD COLUMN email VARCHAR(200)'))
        db.session.commit()
    except Exception:
        db.session.rollback()  # column already exists
    seed_data()
    ensure_default_admin()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
