import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, User, Lesson, LessonProgress, CodeSnippet, CodeStyle, StyleExample
from ai_engine import explain_code, compare_styles, get_ai_provider

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///codementor.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ---------- Auth helpers ----------

def ensure_default_admin():
    admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
    if not User.query.filter_by(username=admin_user).first():
        u = User(username=admin_user, role='admin')
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
        password = request.form.get('password', '')
        role = request.form.get('role', 'student')
        if not username or not password:
            flash('Username and password required.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, role=role if role in ('student', 'admin') else 'student')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', user=current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = (user.role == 'admin')
            flash('Welcome back, {}!'.format(user.username), 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', user=current_user())

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
        ensure_default_admin()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
