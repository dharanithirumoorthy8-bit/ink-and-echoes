import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import Category, Poem, db
from models import Suggestion, User, ApiToken, ActiveViewer

admin_bp = Blueprint('admin', __name__)


def normalize_poem_text(value):
    return ' '.join((value or '').strip().split()).lower()


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
    # Support both regular form POSTS (browser) and JSON sync POSTs (offline sync)
    if request.is_json:
        payload = request.get_json()
        title = (payload.get('title') or '').strip()
        body = (payload.get('body') or '').strip()
        category_name = (payload.get('category') or '').strip()
    else:
        title = (request.form.get('title') or '').strip()
        body = (request.form.get('body') or '').strip()
        category_name = (request.form.get('category') or '').strip()

    if not title or not body:
        if request.is_json:
            return ({'error': 'Title and body required'}, 400)
        flash('Please add both a title and the poem text.')
        return redirect(url_for('admin.admin_index'))

    normalized_title = normalize_poem_text(title)
    normalized_body = normalize_poem_text(body)
    duplicate_poem = None
    for poem in Poem.query.filter_by(published=True).all():
        if normalize_poem_text(poem.title) == normalized_title and normalize_poem_text(poem.body) == normalized_body:
            duplicate_poem = poem
            break

    if duplicate_poem:
        message = f'This poem already exists in the library and was not added again.'
        if request.is_json:
            return jsonify({'ok': False, 'error': 'duplicate', 'message': message})
        flash(message)
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

    # Only handle image when form POST includes file upload
    if not request.is_json:
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
    if request.is_json:
        return jsonify({'ok': True, 'title': title, 'id': poem.id, 'message': 'Poem saved successfully.'})
    flash(f'Poem saved successfully: {title}')
    return redirect(url_for('admin.admin_index'))


@admin_bp.route('/admin/poem/<int:poem_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_poem(poem_id):
    poem = Poem.query.get(poem_id)
    if poem is None:
        flash('Poem not found.')
        return redirect(url_for('admin.admin_index'))

    db.session.delete(poem)
    db.session.commit()
    flash(f'Poem deleted: {poem.title}')
    return redirect(url_for('admin.admin_index'))


@admin_bp.route('/admin/viewers')
@login_required
@admin_required
def admin_viewers():
    tokens = ApiToken.query.order_by(ApiToken.created_at.desc()).all()
    viewers = ActiveViewer.query.order_by(ActiveViewer.last_seen.desc()).all()
    return render_template('admin_viewers.html', tokens=tokens, viewers=viewers)


@admin_bp.route('/admin/viewers/revoke_token', methods=['POST'])
@login_required
@admin_required
def revoke_token():
    token_id = request.form.get('token_id')
    if not token_id:
        flash('Token id required')
        return redirect(url_for('admin.admin_viewers'))
    t = ApiToken.query.get(int(token_id))
    if not t:
        flash('Token not found')
        return redirect(url_for('admin.admin_viewers'))
    db.session.delete(t)
    db.session.commit()
    flash('Token revoked')
    return redirect(url_for('admin.admin_viewers'))


@admin_bp.route('/admin/viewers/remove_viewer', methods=['POST'])
@login_required
@admin_required
def remove_viewer():
    client_id = request.form.get('client_id')
    page = request.form.get('page')
    if not client_id or not page:
        flash('client_id and page required')
        return redirect(url_for('admin.admin_viewers'))
    ActiveViewer.query.filter_by(client_id=client_id, page=page).delete()
    db.session.commit()
    flash('Viewer entry removed')
    return redirect(url_for('admin.admin_viewers'))
