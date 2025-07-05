from flask import Flask, render_template, redirect, request, session, url_for, g
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'secret_key'
DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    get_db().commit()
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    posts = query_db('''
        SELECT posts.*, users.username,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) as like_count,
            (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) as comment_count
        FROM posts JOIN users ON users.id = posts.user_id ORDER BY posts.created_at DESC
    ''')

    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        query_db('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = query_db('SELECT * FROM users WHERE username = ?', [request.form['username']], one=True)
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/post', methods=['POST'])
def post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form['content']
    query_db('INSERT INTO posts (user_id, content) VALUES (?, ?)', (session['user_id'], content))
    return redirect(url_for('index'))

@app.route('/like/<int:post_id>')
def like(post_id):
    user_id = session['user_id']
    exists = query_db('SELECT * FROM likes WHERE user_id=? AND post_id=?', (user_id, post_id), one=True)
    if not exists:
        query_db('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
    return redirect(url_for('index'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    content = request.form['comment']
    query_db('INSERT INTO comments (post_id, user_id, content) VALUES (?, ?, ?)', (post_id, session['user_id'], content))
    return redirect(url_for('index'))

@app.route('/user/<username>')
def profile(username):
    user = query_db('SELECT * FROM users WHERE username=?', (username,), one=True)
    posts = query_db('SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC', (user['id'],))
    is_following = query_db('SELECT * FROM followers WHERE follower_id=? AND followed_id=?', (session['user_id'], user['id']), one=True)
    return render_template('profile.html', user=user, posts=posts, is_following=is_following)

@app.route('/follow/<int:user_id>')
def follow(user_id):
    query_db('INSERT INTO followers (follower_id, followed_id) VALUES (?, ?)', (session['user_id'], user_id))
    return redirect(url_for('profile', username=query_db('SELECT username FROM users WHERE id=?', (user_id,), one=True)['username']))

@app.route('/unfollow/<int:user_id>')
def unfollow(user_id):
    query_db('DELETE FROM followers WHERE follower_id=? AND followed_id=?', (session['user_id'], user_id))
    return redirect(url_for('profile', username=query_db('SELECT username FROM users WHERE id=?', (user_id,), one=True)['username']))

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript(open('schema.sql').read())
        db.commit()

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)