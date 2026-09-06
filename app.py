import os
from datetime import datetime
import click
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from werkzeug.security import check_password_hash
from flask_login import LoginManager, login_required, current_user
from models import db


def create_app():
    # Use instance folder for persistent runtime data (DB, secret key)
    app = Flask(__name__, instance_relative_config=True)

    # Ensure instance folder exists so files persist across restarts
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        pass

    # Load or create a persistent secret key stored in the instance folder
    secret_file = os.path.join(app.instance_path, 'secret_key')
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        try:
            if os.path.exists(secret_file):
                with open(secret_file, 'rb') as fh:
                    secret_key = fh.read().decode('utf-8')
            else:
                secret_key = os.urandom(24).hex()
                with open(secret_file, 'wb') as fh:
                    fh.write(secret_key.encode('utf-8'))
        except Exception:
            # fallback to dev-secret when filesystem is unavailable
            secret_key = 'dev-secret'

    app.config['SECRET_KEY'] = secret_key
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
    app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

    # Prefer explicit DATABASE_URL env var; otherwise use a file inside instance/
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        db_path = os.path.join(app.instance_path, 'ink_and_echoes.db')
        database_url = 'sqlite:///' + os.path.abspath(db_path).replace('\\', '/')

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace(
            'postgres://', 'postgresql://', 1
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', '0') == '1'

    db.init_app(app)

    # In-memory active viewers store to avoid persisting client IDs
    import threading
    from datetime import datetime, timedelta
    ACTIVE_VIEWERS = {}
    ACTIVE_VIEWERS_LOCK = threading.Lock()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from auth import auth_bp
    app.register_blueprint(auth_bp)

    from admin import admin_bp
    app.register_blueprint(admin_bp)

    from ai import ai_bp
    app.register_blueprint(ai_bp)

    # expose some site-wide values to templates
    @app.context_processor
    def inject_site_stats():
        try:
            from models import PageView, Poem, Category, Favorite
            pv = PageView.query.filter_by(page='poems').first()
            count = pv.count if pv else 0
            total_poems = Poem.query.filter_by(published=True).count()
            total_categories = Category.query.count()
            total_favorites = Favorite.query.count()
        except Exception:
            count = 0
            total_poems = 0
            total_categories = 0
            total_favorites = 0
        return {
            'poems_total_views': count,
            'total_poems': total_poems,
            'total_categories': total_categories,
            'total_favorites': total_favorites,
        }

    @app.cli.command('init-db')
    def init_db():
        """Initialize the database (create tables) and ensure admin user exists."""
        from models import db as _db
        _db.create_all()
        try:
            from auth import get_admin_user
            get_admin_user()
        except Exception:
            pass
        print('Database initialized and admin user ensured.')

    @app.cli.command('create-admin')
    @click.option('--username', '-u', required=True, help='Admin username')
    @click.option('--password', '-p', required=True, help='Admin password')
    def create_admin(username, password):
        """Create or update an administrator account."""
        from models import User, db as _db
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=f'{username}@admin.local', is_admin=True)
            user.set_password(password)
            _db.session.add(user)
            _db.session.commit()
            print(f'Created admin user: {username}')
        else:
            user.is_admin = True
            user.set_password(password)
            _db.session.commit()
            print(f'Updated admin user: {username}')

    @app.cli.command('create-token')
    @click.option('--username', '-u', required=True, help='Admin username to attach token')
    @click.option('--name', '-n', required=False, help='Token name')
    def create_token(username, name):
        """Create a new API token for an admin user and print the raw token."""
        from models import User, ApiToken, db as _db
        import secrets
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if not user or not getattr(user, 'is_admin', False):
            print('User not found or not an admin')
            return
        raw = secrets.token_urlsafe(32)
        token_hash = generate_password_hash(raw)
        t = ApiToken(user_id=user.id, name=name, token_hash=token_hash)
        _db.session.add(t)
        _db.session.commit()
        print('Created token for', username)
        print('Raw token (store this somewhere safe):')
        print(raw)

    @app.cli.command('backup-db')
    def backup_db_cli():
        """Create a timestamped backup copy of the instance SQLite database."""
        import shutil, datetime
        src = os.path.join(app.instance_path, 'ink_and_echoes.db')
        if not os.path.exists(src):
            print('No database file to backup:', src)
            return
        backups_dir = os.path.join(app.instance_path, 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        dst = os.path.join(backups_dir, f'ink_and_echoes-{ts}.db')
        shutil.copy2(src, dst)
        print('Backed up DB to', dst)

    @app.route('/')
    def index():
        from models import Poem, PageView, Category

        page_view = PageView.query.filter_by(page='home').first()
        if page_view is None:
            page_view = PageView(page='home', count=1)
            db.session.add(page_view)
        else:
            page_view.count += 1
        db.session.commit()

        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).limit(3).all()
        recent_poem_ids = {
            poem.id for poem in poems
            if poem.created_at and (datetime.utcnow() - poem.created_at).days <= 7
        }
        latest_poem = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).first()
        has_new_poem = bool(latest_poem and latest_poem.created_at and (datetime.utcnow() - latest_poem.created_at).days <= 7)
        
        # Get featured poem
        featured_poem = Poem.query.filter_by(published=True, is_featured=True).first()
        
        # Get categories for collection section
        categories = Category.query.all()
        
        return render_template(
            'index.html',
            poems=poems,
            total_views=page_view.count,
            recent_poem_ids=recent_poem_ids,
            latest_poem=latest_poem,
            has_new_poem=has_new_poem,
            featured_poem=featured_poem,
            categories=categories,
        )

    @app.route('/poems')
    def poems():
        from models import Poem, PageView, Category
        
        # increment poems page view counter
        page_view = PageView.query.filter_by(page='poems').first()
        if page_view is None:
            page_view = PageView(page='poems', count=1)
            db.session.add(page_view)
        else:
            page_view.count += 1
        db.session.commit()

        # Get filter, search, and sort parameters
        category_filter = request.args.get('category', '').strip()
        search_query = request.args.get('search', '').strip()
        sort_by = request.args.get('sort', 'newest')  # newest, oldest, a-z

        # Base query
        query = Poem.query.filter_by(published=True)

        # Apply category filter
        if category_filter and category_filter != 'all':
            query = query.filter_by(category_id=int(category_filter))

        # Apply search
        if search_query:
            search_pattern = f'%{search_query}%'
            query = query.filter(
                (Poem.title.ilike(search_pattern)) |
                (Poem.body.ilike(search_pattern)) |
                (Poem.description.ilike(search_pattern))
            )

        # Apply sorting
        if sort_by == 'oldest':
            query = query.order_by(Poem.created_at.asc())
        elif sort_by == 'a-z':
            query = query.order_by(Poem.title.asc())
        else:  # newest (default)
            query = query.order_by(Poem.created_at.desc())

        poems = query.all()
        categories = Category.query.all()
        
        # Get user's favorite poem IDs if logged in
        user_favorites = []
        if current_user.is_authenticated:
            from models import Favorite
            user_favorites = [fav.poem_id for fav in Favorite.query.filter_by(user_id=current_user.id).all()]

        return render_template(
            'poems.html',
            poems=poems,
            categories=categories,
            user_favorites=user_favorites,
            current_sort=sort_by,
            current_search=search_query,
            current_category=category_filter,
        )

    @app.route('/poems/full')
    def poems_full():
        from models import Poem
        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).all()
        return render_template('poems.html', poems=poems, require_login=False, full_view=True)

    @app.route('/poem/<int:poem_id>')
    def poem_detail(poem_id):
        from models import Poem, Favorite
        
        poem = Poem.query.get(poem_id)
        if poem is None or not poem.published:
            flash('This verse seems to have wandered beyond the margins.')
            return redirect(url_for('poems'))

        # Increment view count
        from models import History
        if current_user.is_authenticated:
            history = History(user_id=current_user.id, poem_id=poem_id)
            db.session.add(history)
            db.session.commit()

        # Check if user has favorited this poem
        is_favorited = False
        if current_user.is_authenticated:
            favorite = Favorite.query.filter_by(user_id=current_user.id, poem_id=poem_id).first()
            is_favorited = favorite is not None

        # Get neighboring poems for prev/next navigation
        all_poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).all()
        poem_ids = [p.id for p in all_poems]
        
        current_index = poem_ids.index(poem_id) if poem_id in poem_ids else -1
        prev_poem = all_poems[current_index - 1] if current_index > 0 else None
        next_poem = all_poems[current_index + 1] if current_index >= 0 and current_index < len(all_poems) - 1 else None

        return render_template(
            'poem_detail.html',
            poem=poem,
            is_favorited=is_favorited,
            prev_poem=prev_poem,
            next_poem=next_poem,
        )

    @app.route('/favorites')
    @login_required
    def favorites():
        from models import Poem, Favorite

        favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
        favorite_poems = [Poem.query.get(fav.poem_id) for fav in favorites]
        favorite_poems = [p for p in favorite_poems if p and p.published]

        return render_template(
            'favorites.html',
            poems=favorite_poems,
            total_favorites=len(favorite_poems),
        )

    @app.route('/api/v1/favorite/<int:poem_id>', methods=['POST'])
    @login_required
    def api_favorite_poem(poem_id):
        from models import Poem, Favorite

        poem = Poem.query.get(poem_id)
        if poem is None or not poem.published:
            return jsonify({'error': 'Poem not found'}), 404

        existing_favorite = Favorite.query.filter_by(user_id=current_user.id, poem_id=poem_id).first()
        
        if existing_favorite:
            db.session.delete(existing_favorite)
            db.session.commit()
            return jsonify({'success': True, 'favorited': False, 'message': 'Removed from favorites'})
        else:
            new_favorite = Favorite(user_id=current_user.id, poem_id=poem_id)
            db.session.add(new_favorite)
            db.session.commit()
            return jsonify({'success': True, 'favorited': True, 'message': 'Added to favorites'})

    @app.route('/chat')
    def chat():
        return render_template('chat.html')

    # Simple JSON API (v1)
    @app.route('/api/v1/poems')
    def api_poems():
        from models import Poem, Category
        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).all()
        out = []
        for p in poems:
            cat_name = None
            if p.category_id:
                c = Category.query.get(p.category_id)
                cat_name = c.name if c else None
            out.append({
                'id': p.id,
                'title': p.title,
                'body': p.body,
                'category': cat_name,
                'created_at': p.created_at.isoformat() if p.created_at else None,
            })
        return jsonify(out)

    @app.route('/api/v1/notifications')
    def api_notifications():
        from models import Poem

        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).limit(10).all()
        return jsonify([
            {
                'id': poem.id,
                'title': poem.title,
                'created_at': poem.created_at.isoformat() if poem.created_at else None,
                'url': url_for('poems'),
            }
            for poem in poems
        ])

    @app.route('/api/v1/poems/<int:poem_id>')
    def api_poem_detail(poem_id):
        from models import Poem, Category
        p = Poem.query.get(poem_id)
        if p is None or not p.published:
            return (jsonify({'error': 'not found'}), 404)
        cat_name = None
        if p.category_id:
            c = Category.query.get(p.category_id)
            cat_name = c.name if c else None
        return jsonify({
            'id': p.id,
            'title': p.title,
            'body': p.body,
            'category': cat_name,
            'created_at': p.created_at.isoformat() if p.created_at else None,
        })

    def _is_admin_request():
        # Allow when logged in as admin
        try:
            if getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_admin', False):
                return True
        except Exception:
            pass

        # Allow X-API-KEY header equal to SECRET_KEY
        api_key = request.headers.get('X-API-KEY')
        if api_key and api_key == app.config.get('SECRET_KEY'):
            return True

        # Allow HTTP Basic auth: username:password
        auth = request.headers.get('Authorization')
        if auth and auth.startswith('Basic '):
            try:
                import base64
                from models import User
                creds = base64.b64decode(auth.split(' ', 1)[1]).decode('utf-8')
                username, password = creds.split(':', 1)
                user = User.query.filter((User.username == username) | (User.email == username)).first()
                if user and user.check_password(password) and getattr(user, 'is_admin', False):
                    return True
            except Exception:
                pass

        # Allow Bearer token: check ApiToken table
        if auth and auth.startswith('Bearer '):
            try:
                token = auth.split(' ', 1)[1]
                from models import ApiToken
                # check all tokens (hashed) for a match
                for t in ApiToken.query.all():
                    if check_password_hash(t.token_hash, token) and getattr(t.user, 'is_admin', False):
                        return True
            except Exception:
                pass
        return False

    @app.route('/api/v1/poems', methods=['POST'])
    def api_poems_create():
        if not _is_admin_request():
            return (jsonify({'error': 'unauthorized'}), 401)
        if not request.is_json:
            return (jsonify({'error': 'expected JSON body'}), 400)
        payload = request.get_json()
        title = (payload.get('title') or '').strip()
        body = (payload.get('body') or '').strip()
        category_name = (payload.get('category') or '').strip()
        published = bool(payload.get('published', True))
        if not title or not body:
            return (jsonify({'error': 'title and body required'}), 400)

        from models import Poem, Category, db as _db

        def normalize_text(s):
            return ' '.join((s or '').strip().split()).lower()

        normalized_title = normalize_text(title)
        normalized_body = normalize_text(body)
        for poem in Poem.query.filter_by(published=True).all():
            if normalize_text(poem.title) == normalized_title and normalize_text(poem.body) == normalized_body:
                return (jsonify({'ok': False, 'error': 'duplicate'}), 409)

        category = None
        if category_name:
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name)
                _db.session.add(category)
                _db.session.flush()

        poem = Poem(title=title, body=body, category_id=category.id if category else None, published=published)
        _db.session.add(poem)
        _db.session.commit()
        return jsonify({'ok': True, 'id': poem.id, 'title': poem.title})

    # Active viewers endpoints
    @app.route('/api/v1/viewers/ping', methods=['POST'])
    def api_viewers_ping():
        if not request.is_json:
            return (jsonify({'error':'expected JSON'}), 400)
        payload = request.get_json()
        client_id = (payload.get('client_id') or '').strip()
        page = (payload.get('page') or '').strip()
        if not client_id or not page:
            return (jsonify({'error':'client_id and page required'}), 400)
        from models import ActiveViewer, db as _db
        from datetime import datetime
        av = ActiveViewer.query.filter_by(client_id=client_id, page=page).first()
        if av is None:
            av = ActiveViewer(client_id=client_id, page=page, last_seen=datetime.utcnow())
            _db.session.add(av)
        else:
            av.last_seen = datetime.utcnow()
        _db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/v1/viewers/<page>')
    def api_viewers_count(page):
        from models import ActiveViewer
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(seconds=60)
        count = ActiveViewer.query.filter(ActiveViewer.page==page, ActiveViewer.last_seen>=cutoff).count()
        return jsonify({'count': count})

    @app.route('/suggestions', methods=['GET', 'POST'])
    def suggestions():
        if request.method == 'POST':
            from models import Suggestion

            message = (request.form.get('message') or '').strip()
            user_id = current_user.id if getattr(current_user, 'is_authenticated', False) else None
            if message:
                s = Suggestion(user_id=user_id, message=message)
                db.session.add(s)
                db.session.commit()
                flash('Your suggestion has been saved to the margins.')
            else:
                flash('Write a little note before sending it.')
            return redirect(url_for('suggestions'))
        return render_template('suggestions.html')

    @app.route('/admin/suggestions')
    @login_required
    def admin_suggestions():
        from models import Suggestion, User
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.')
            return redirect(url_for('index'))
        suggestions = Suggestion.query.order_by(Suggestion.created_at.desc()).all()
        # attach user info when available
        results = []
        for s in suggestions:
            user = User.query.get(s.user_id) if s.user_id else None
            results.append({'suggestion': s, 'user': user})
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin_suggestions.html', suggestions=results, users=users)

    return app


app = create_app()

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
