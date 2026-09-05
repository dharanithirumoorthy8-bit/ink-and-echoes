import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_required, current_user
from models import db


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
    app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'sqlite:///ink_and_echoes.db'
    )
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace(
            'postgres://', 'postgresql://', 1
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', '0') == '1'

    db.init_app(app)

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

    @app.route('/')
    def index():
        from models import Poem, PageView

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
        return render_template(
            'index.html',
            poems=poems,
            total_views=page_view.count,
            recent_poem_ids=recent_poem_ids,
            latest_poem=latest_poem,
            has_new_poem=has_new_poem,
        )

    @app.route('/poems')
    def poems():
        from models import Poem
        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).all()
        return render_template('poems.html', poems=poems)

    @app.route('/poems/full')
    @login_required
    def poems_full():
        from models import Poem
        poems = Poem.query.filter_by(published=True).order_by(Poem.created_at.desc()).all()
        return render_template('poems.html', poems=poems, require_login=False, full_view=True)

    @app.route('/chat')
    def chat():
        return render_template('chat.html')

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
