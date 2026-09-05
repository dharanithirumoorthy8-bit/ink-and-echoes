import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import Category, Poem, db
from models import Suggestion, User

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Login required to manage poems.')
            return redirect(url_for('auth.login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return wrapped


@admin_bp.route('/admin')
@login_required
@admin_required
def admin_index():
    poems = Poem.query.order_by(Poem.created_at.desc()).all()
    categories = Category.query.all()
    users = User.query.order_by(User.created_at.desc()).all()
    suggestions = Suggestion.query.order_by(Suggestion.created_at.desc()).all()
    return render_template('admin.html', poems=poems, categories=categories, users=users, suggestions=suggestions)


@admin_bp.route('/admin/poem/new', methods=['POST'])
@login_required
@admin_required
def admin_new_poem():
    title = (request.form.get('title') or '').strip()
    body = (request.form.get('body') or '').strip()
    category_name = (request.form.get('category') or '').strip()

    if not title or not body:
        flash('Please add both a title and the poem text.')
        return redirect(url_for('admin.admin_index'))

    category = None
    if category_name:
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.flush()

    poem = Poem(title=title, body=body, category_id=category.id if category else None, published=True)
    db.session.add(poem)

    image_file = request.files.get('profile_image')
    if image_file and image_file.filename:
        allowed = {'.png', '.jpg', '.jpeg', '.webp'}
        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext in allowed:
            upload_dir = os.path.join(current_app.static_folder, 'img')
            os.makedirs(upload_dir, exist_ok=True)
            filename = 'profile-portrait' + ext
            image_file.save(os.path.join(upload_dir, filename))
            flash('Your profile image was updated.')

    db.session.commit()
    flash(f'New poem published: {title}')
    return redirect(url_for('admin.admin_index'))
