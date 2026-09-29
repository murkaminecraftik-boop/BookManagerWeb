import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secure_secret_key_8f92a1')
JWT_SECRET = os.environ.get('JWT_SECRET', app.secret_key)

TOKEN_COOKIE = 'ath_token'
TOKEN_TTL = timedelta(days=7)
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{3,32}$')

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'library.db'))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                year INTEGER NOT NULL,
                genre TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (user_id, book_id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books (title)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_books_year ON books (year)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ratings_book ON ratings (book_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings (user_id)')
        conn.commit()
    finally:
        conn.close()


def clean_text(value):
    return (value or '').strip()


def parse_year(raw, default=None):
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if 0 <= value <= 9999 else default


def create_token(user_id, username):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'username': username,
        'iat': now,
        'exp': now + TOKEN_TTL
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        user_id = int(payload.get('sub', 0))
        username = payload.get('username', '')
        if user_id <= 0 or not username:
            return None
        return {'id': user_id, 'username': username}
    except (jwt.PyJWTError, TypeError, ValueError):
        return None


@app.before_request
def load_logged_in_user():
    token = request.cookies.get(TOKEN_COOKIE)
    g.user = decode_token(token) if token else None


@app.context_processor
def inject_current_user():
    return {'current_user': g.get('user')}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get('user'):
            flash('Please log in to rate books.', 'error')
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def set_auth_cookie(response, user_id, username):
    token = create_token(user_id, username)
    response.set_cookie(
        TOKEN_COOKIE,
        token,
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite='Lax',
        secure=request.is_secure,
        path='/'
    )
    return response


def safe_next_url(default):
    target = request.args.get('next') or request.form.get('next') or ''
    if target.startswith('/') and not target.startswith('//'):
        return target
    return default


@app.route('/')
def index():
    search_query = clean_text(request.args.get('search', ''))
    sort_order = request.args.get('sort', '')

    query = 'SELECT * FROM books'
    params = []

    if search_query:
        query += ' WHERE LOWER(title) LIKE LOWER(?)'
        params.append(f'%{search_query}%')

    if sort_order == 'asc':
        query += ' ORDER BY year ASC'
    elif sort_order == 'desc':
        query += ' ORDER BY year DESC'

    rows = []
    total_books = 0
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
            rating_rows = conn.execute(
                'SELECT book_id, AVG(rating) AS avg_rating, COUNT(*) AS rating_count '
                'FROM ratings GROUP BY book_id'
            ).fetchall()
            my_rows = []
            if g.get('user'):
                my_rows = conn.execute(
                    'SELECT book_id, rating FROM ratings WHERE user_id = ?',
                    (g.user['id'],)
                ).fetchall()
        finally:
            conn.close()

        rating_map = {r['book_id']: r for r in rating_rows}
        my_map = {r['book_id']: r['rating'] for r in my_rows}
        books = []
        for row in rows:
            entry = dict(row)
            agg = rating_map.get(entry['id'])
            entry['avg_rating'] = round(agg['avg_rating'], 1) if agg else None
            entry['rating_count'] = agg['rating_count'] if agg else 0
            entry['my_rating'] = my_map.get(entry['id'])
            books.append(entry)
    except sqlite3.Error:
        books = []
        flash('Could not read the library database.', 'error')

    return render_template('index.html', books=books, total_books=total_books, search_query=search_query)


@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if g.get('user'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = clean_text(request.form.get('username'))
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''

        if not USERNAME_PATTERN.match(username):
            flash('Username must be 3-32 characters: letters, numbers, dots, dashes, underscores.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            created_id = None
            try:
                conn = get_db_connection()
                try:
                    cursor = conn.execute(
                        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                        (username, generate_password_hash(password))
                    )
                    conn.commit()
                    created_id = cursor.lastrowid
                finally:
                    conn.close()
            except sqlite3.IntegrityError:
                flash('That username is already taken.', 'error')
            except sqlite3.Error:
                flash('Could not create your account. Please try again.', 'error')

            if created_id:
                resp = redirect(url_for('index'))
                set_auth_cookie(resp, created_id, username)
                flash(f'Welcome to Athenaeum, {username}! You can now rate books.', 'success')
                return resp

    return render_template('signup.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.get('user'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = clean_text(request.form.get('username'))
        password = request.form.get('password') or ''

        user = None
        try:
            conn = get_db_connection()
            try:
                user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            flash('Could not reach the database. Please try again.', 'error')

        if user is not None and check_password_hash(user['password_hash'], password):
            resp = redirect(safe_next_url(url_for('index')))
            set_auth_cookie(resp, user['id'], user['username'])
            flash(f"Welcome back, {user['username']}!", 'success')
            return resp

        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout', methods=('POST',))
def logout():
    resp = redirect(url_for('index'))
    resp.delete_cookie(TOKEN_COOKIE, path='/')
    flash('You have been logged out.', 'success')
    return resp


@app.route('/rate/<int:book_id>', methods=('POST',))
@login_required
def rate(book_id):
    raw = request.form.get('rating', '')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0

    if not 1 <= value <= 5:
        flash('Ratings must be between 1 and 5 stars.', 'error')
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        try:
            book = conn.execute('SELECT id, title FROM books WHERE id = ?', (book_id,)).fetchone()
            if book is None:
                flash('That book no longer exists.', 'error')
                return redirect(url_for('index'))
            conn.execute('''
                INSERT INTO ratings (user_id, book_id, rating)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id, book_id)
                DO UPDATE SET rating = excluded.rating, updated_at = datetime('now')
            ''', (g.user['id'], book_id, value))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        flash('Could not save your rating. Please try again.', 'error')
        return redirect(url_for('index'))

    title = book['title']
    flash(f'You rated "{title}" {value}/5 stars!', 'success')
    return redirect(url_for('index'))


@app.route('/add', methods=('GET', 'POST'))
def add():
    if request.method == 'POST':
        title = clean_text(request.form.get('title'))
        author = clean_text(request.form.get('author'))
        year_raw = clean_text(request.form.get('year'))
        genre = clean_text(request.form.get('genre'))

        if not title or not author or not year_raw or not genre:
            flash('All fields are required!', 'error')
        else:
            year_val = parse_year(year_raw, default=0)
            try:
                conn = get_db_connection()
                try:
                    conn.execute('INSERT INTO books (title, author, year, genre) VALUES (?, ?, ?, ?)',
                                 (title, author, year_val, genre))
                    conn.commit()
                finally:
                    conn.close()
                flash('Book successfully added to your catalog!', 'success')
                return redirect(url_for('index'))
            except sqlite3.Error:
                flash('Could not save the book. Please try again.', 'error')

    return render_template('add.html')


@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit(id):
    conn = get_db_connection()
    try:
        book = conn.execute('SELECT * FROM books WHERE id = ?', (id,)).fetchone()
    finally:
        conn.close()

    if book is None:
        flash('Book not found!', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = clean_text(request.form.get('title'))
        author = clean_text(request.form.get('author'))
        year_raw = clean_text(request.form.get('year'))
        genre = clean_text(request.form.get('genre'))

        if not title or not author or not year_raw or not genre:
            flash('All fields are required!', 'error')
            return redirect(url_for('edit', id=id))

        year_val = parse_year(year_raw)
        if year_val is None:
            flash('Year must be a valid number.', 'error')
            return redirect(url_for('edit', id=id))

        try:
            conn = get_db_connection()
            try:
                conn.execute('UPDATE books SET title = ?, author = ?, year = ?, genre = ? WHERE id = ?',
                             (title, author, year_val, genre, id))
                conn.commit()
            finally:
                conn.close()
            flash('Book successfully updated!', 'success')
            return redirect(url_for('index'))
        except sqlite3.Error:
            flash('Could not update the book. Please try again.', 'error')

    return render_template('edit.html', book=book)


@app.route('/delete/<int:id>', methods=('POST',))
def delete(id):
    try:
        conn = get_db_connection()
        try:
            cursor = conn.execute('DELETE FROM books WHERE id = ?', (id,))
            conn.commit()
            deleted = cursor.rowcount
        finally:
            conn.close()
    except sqlite3.Error:
        flash('Could not delete the book. Please try again.', 'error')
        return redirect(url_for('index'))

    if deleted:
        flash('Book successfully deleted from collection.', 'success')
    else:
        flash('That book was not found in your catalog.', 'error')
    return redirect(url_for('index'))


@app.errorhandler(404)
def handle_not_found(_error):
    flash('The page you requested does not exist.', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def handle_server_error(_error):
    flash('Something went wrong on our side. Please try again.', 'error')
    return redirect(url_for('index'))


init_db()

if __name__ == '__main__':
    app.run(
        debug=os.environ.get('FLASK_DEBUG', '1') == '1',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5000'))
    )