import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
)

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (
    Category,
    Poem,
    Favorite,
    Suggestion,
    User,
    ApiToken,
    ActiveViewer,
    db,
)


admin_bp = Blueprint('admin', __name__)


# =========================================================
# HELPERS
# =========================================================

def normalize_poem_text(value):
    return ' '.join(
        (value or '').strip().split()
    ).lower()


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


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route('/admin')
@login_required
@admin_required
def admin_index():

    poems = Poem.query.order_by(
        Poem.created_at.desc()
    ).all()

    categories = Category.query.order_by(
        Category.name.asc()
    ).all()

    users = User.query.order_by(
        User.created_at.desc()
    ).all()

    suggestions = Suggestion.query.order_by(
        Suggestion.created_at.desc()
    ).all()

    total_poems = (
        Poem.query
        .filter_by(published=True)
        .count()
    )

    # Safe favorite count.
    # The previous raw SQL query was causing the /admin 500.
    try:
        total_favorites = Favorite.query.count()
    except Exception:
        db.session.rollback()
        total_favorites = 0

    return render_template(
        'admin.html',
        poems=poems,
        categories=categories,
        users=users,
        suggestions=suggestions,
        total_poems=total_poems,
        total_categories=len(categories),
        total_favorites=total_favorites,
    )


# =========================================================
# ADD NEW POEM
# =========================================================

@admin_bp.route('/admin/poem/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_new_poem():

    categories = Category.query.order_by(
        Category.name.asc()
    ).all()

    if request.method == 'POST':

        # -------------------------------------------------
        # JSON / OFFLINE SYNC
        # -------------------------------------------------

        if request.is_json:

            payload = request.get_json() or {}

            title = (
                payload.get('title') or ''
            ).strip()

            body = (
                payload.get('body') or ''
            ).strip()

            description = (
                payload.get('description') or ''
            ).strip()

            category_id = payload.get(
                'category_id'
            )

            tags = (
                payload.get('tags') or ''
            ).strip()

        # -------------------------------------------------
        # NORMAL BROWSER FORM
        # -------------------------------------------------

        else:

            title = (
                request.form.get('title') or ''
            ).strip()

            body = (
                request.form.get('body') or ''
            ).strip()

            description = (
                request.form.get('description') or ''
            ).strip()

            category_id = request.form.get(
                'category_id'
            )

            tags = (
                request.form.get('tags') or ''
            ).strip()

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not title or not body:

            if request.is_json:
                return jsonify({
                    'error': 'Title and body required'
                }), 400

            flash(
                'Please add both a title and the poem text.'
            )

            return redirect(
                url_for('admin.admin_index')
            )

        # -------------------------------------------------
        # DUPLICATE CHECK
        # -------------------------------------------------

        normalized_title = normalize_poem_text(
            title
        )

        normalized_body = normalize_poem_text(
            body
        )

        duplicate_poem = None

        for poem in Poem.query.filter_by(
            published=True
        ).all():

            if (
                normalize_poem_text(poem.title)
                == normalized_title
                and
                normalize_poem_text(poem.body)
                == normalized_body
            ):
                duplicate_poem = poem
                break

        if duplicate_poem:

            message = (
                'This poem already exists in the library '
                'and was not added again.'
            )

            if request.is_json:

                return jsonify({
                    'ok': False,
                    'error': 'duplicate',
                    'message': message,
                }), 409

            flash(message)

            return redirect(
                url_for('admin.admin_index')
            )

        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        category = None

        if category_id:

            try:

                category = Category.query.get(
                    int(category_id)
                )

            except (ValueError, TypeError):

                category = None

        # -------------------------------------------------
        # CREATE POEM
        # -------------------------------------------------

        poem = Poem(
            title=title,
            body=body,
            description=description or None,
            category_id=(
                category.id
                if category
                else None
            ),
            tags=tags or None,
            published=True,
        )

        db.session.add(poem)

        # -------------------------------------------------
        # COVER IMAGE
        # -------------------------------------------------

        if not request.is_json:

            # IMPORTANT:
            # admin.html uses profile_image
            image_file = request.files.get(
                'profile_image'
            )

            if (
                image_file
                and image_file.filename
            ):

                allowed = {
                    '.png',
                    '.jpg',
                    '.jpeg',
                    '.webp',
                }

                ext = os.path.splitext(
                    image_file.filename
                )[1].lower()

                if ext in allowed:

                    # Flush first so poem.id exists.
                    db.session.flush()

                    upload_dir = os.path.join(
                        current_app.static_folder,
                        'img',
                        'covers',
                    )

                    os.makedirs(
                        upload_dir,
                        exist_ok=True,
                    )

                    safe_title = secure_filename(
                        title.lower().replace(
                            ' ',
                            '-'
                        )
                    )

                    filename = secure_filename(
                        f'{safe_title}-{poem.id}{ext}'
                    )

                    image_path = os.path.join(
                        upload_dir,
                        filename,
                    )

                    image_file.save(
                        image_path
                    )

                    poem.cover_image = (
                        f'/static/img/covers/{filename}'
                    )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        try:

            db.session.commit()

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                'Failed to save poem: %s',
                exc
            )

            if request.is_json:

                return jsonify({
                    'ok': False,
                    'error': 'database_error',
                    'message': 'Could not save poem.',
                }), 500

            flash(
                'Could not save the poem. Please try again.'
            )

            return redirect(
                url_for('admin.admin_index')
            )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        if request.is_json:

            return jsonify({
                'ok': True,
                'title': title,
                'id': poem.id,
                'message': 'Poem saved successfully.',
            })

        flash(
            f'Your poem has found its place in '
            f'Moonlit Marginalia: {title}'
        )

        return redirect(
            url_for('admin.admin_index')
        )

    return render_template(
        'admin_new_poem.html',
        categories=categories,
    )


# =========================================================
# EDIT POEM
# =========================================================

@admin_bp.route(
    '/admin/poem/<int:poem_id>/edit',
    methods=['GET', 'POST']
)
@login_required
@admin_required
def admin_edit_poem(poem_id):

    poem = Poem.query.get(poem_id)

    if poem is None:

        flash('Poem not found.')

        return redirect(
            url_for('admin.admin_index')
        )

    categories = Category.query.order_by(
        Category.name.asc()
    ).all()

    if request.method == 'POST':

        title = (
            request.form.get('title') or ''
        ).strip()

        body = (
            request.form.get('body') or ''
        ).strip()

        description = (
            request.form.get('description') or ''
        ).strip()

        category_id = request.form.get(
            'category_id'
        )

        tags = (
            request.form.get('tags') or ''
        ).strip()

        if not title or not body:

            flash(
                'Please add both a title and the poem text.'
            )

            return redirect(
                url_for(
                    'admin.admin_edit_poem',
                    poem_id=poem_id,
                )
            )

        # -------------------------------------------------
        # DUPLICATE CHECK
        # -------------------------------------------------

        normalized_title = normalize_poem_text(
            title
        )

        normalized_body = normalize_poem_text(
            body
        )

        for other_poem in Poem.query.filter_by(
            published=True
        ).all():

            if other_poem.id == poem_id:
                continue

            if (
                normalize_poem_text(
                    other_poem.title
                ) == normalized_title
                and
                normalize_poem_text(
                    other_poem.body
                ) == normalized_body
            ):

                flash(
                    'A poem with this title and text '
                    'already exists.'
                )

                return redirect(
                    url_for(
                        'admin.admin_edit_poem',
                        poem_id=poem_id,
                    )
                )

        # -------------------------------------------------
        # UPDATE POEM
        # -------------------------------------------------

        poem.title = title
        poem.body = body
        poem.description = description or None
        poem.tags = tags or None

        # Category
        if category_id:

            try:

                category = Category.query.get(
                    int(category_id)
                )

                poem.category_id = (
                    category.id
                    if category
                    else None
                )

            except (ValueError, TypeError):

                poem.category_id = None

        else:

            poem.category_id = None

        # -------------------------------------------------
        # UPDATE COVER
        # -------------------------------------------------

        image_file = request.files.get(
            'profile_image'
        )

        if (
            image_file
            and image_file.filename
        ):

            allowed = {
                '.png',
                '.jpg',
                '.jpeg',
                '.webp',
            }

            ext = os.path.splitext(
                image_file.filename
            )[1].lower()

            if ext in allowed:

                upload_dir = os.path.join(
                    current_app.static_folder,
                    'img',
                    'covers',
                )

                os.makedirs(
                    upload_dir,
                    exist_ok=True,
                )

                safe_title = secure_filename(
                    title.lower().replace(
                        ' ',
                        '-'
                    )
                )

                filename = secure_filename(
                    f'{safe_title}-{poem_id}{ext}'
                )

                image_file.save(
                    os.path.join(
                        upload_dir,
                        filename,
                    )
                )

                poem.cover_image = (
                    f'/static/img/covers/{filename}'
                )

                flash(
                    'Poem cover image was updated.'
                )

        try:

            db.session.commit()

        except Exception as exc:

            db.session.rollback()

            current_app.logger.exception(
                'Failed to update poem: %s',
                exc
            )

            flash(
                'Could not update the poem.'
            )

            return redirect(
                url_for(
                    'admin.admin_edit_poem',
                    poem_id=poem_id,
                )
            )

        flash(
            f'Poem updated: {title}'
        )

        return redirect(
            url_for('admin.admin_index')
        )

    return render_template(
        'admin_edit_poem.html',
        poem=poem,
        categories=categories,
    )


# =========================================================
# DELETE POEM
# =========================================================

@admin_bp.route(
    '/admin/poem/<int:poem_id>/delete',
    methods=['POST']
)
@login_required
@admin_required
def admin_delete_poem(poem_id):

    poem = Poem.query.get(poem_id)

    if poem is None:

        flash('Poem not found.')

        return redirect(
            url_for('admin.admin_index')
        )

    title = poem.title

    try:

        db.session.delete(poem)
        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            'Failed to delete poem: %s',
            exc
        )

        flash(
            'Could not delete the poem.'
        )

        return redirect(
            url_for('admin.admin_index')
        )

    flash(
        f'Poem removed from the collection: {title}'
    )

    return redirect(
        url_for('admin.admin_index')
    )


# =========================================================
# FEATURE / UNFEATURE POEM
# =========================================================

@admin_bp.route(
    '/admin/poem/<int:poem_id>/feature',
    methods=['POST']
)
@login_required
@admin_required
def admin_feature_poem(poem_id):

    poem = Poem.query.get(poem_id)

    if poem is None:

        return jsonify({
            'error': 'Poem not found'
        }), 404

    try:

        # Remove featured status from others
        Poem.query.filter(
            Poem.id != poem_id
        ).update({
            'is_featured': False
        })

        # Toggle current poem
        poem.is_featured = not poem.is_featured

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            'Failed to feature poem: %s',
            exc
        )

        return jsonify({
            'success': False,
            'error': 'Could not update featured status',
        }), 500

    return jsonify({

        'success': True,

        'is_featured': poem.is_featured,

        'message': (
            f'Featured status: '
            f'{"On" if poem.is_featured else "Off"}'
        ),

    })


# =========================================================
# CATEGORIES
# =========================================================

@admin_bp.route(
    '/admin/categories',
    methods=['GET', 'POST']
)
@login_required
@admin_required
def admin_categories():

    if request.method == 'POST':

        action = request.form.get(
            'action'
        )

        # -------------------------------------------------
        # ADD CATEGORY
        # -------------------------------------------------

        if action == 'add':

            name = (
                request.form.get('name') or ''
            ).strip()

            if not name:

                flash(
                    'Category name required.'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            if Category.query.filter_by(
                name=name
            ).first():

                flash(
                    'Category already exists.'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            category = Category(
                name=name
            )

            db.session.add(category)

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                flash(
                    'Could not add category.'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            flash(
                f'Category added: {name}'
            )

        # -------------------------------------------------
        # DELETE CATEGORY
        # -------------------------------------------------

        elif action == 'delete':

            category_id = (
                request.form.get(
                    'category_id'
                )
            )

            try:

                category = Category.query.get(
                    int(category_id)
                )

            except (ValueError, TypeError):

                category = None

            if category is None:

                flash(
                    'Category not found.'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            poems_using = (
                Poem.query
                .filter_by(
                    category_id=category.id
                )
                .count()
            )

            if poems_using > 0:

                flash(
                    f'Cannot delete category in use '
                    f'by {poems_using} poem(s).'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            category_name = category.name

            db.session.delete(category)

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                flash(
                    'Could not delete category.'
                )

                return redirect(
                    url_for(
                        'admin.admin_categories'
                    )
                )

            flash(
                f'Category deleted: {category_name}'
            )

        return redirect(
            url_for('admin.admin_categories')
        )

    # -----------------------------------------------------
    # GET CATEGORIES
    # -----------------------------------------------------

    categories = Category.query.order_by(
        Category.name.asc()
    ).all()

    category_usage = {}

    for cat in categories:

        category_usage[cat.id] = (
            Poem.query
            .filter_by(
                category_id=cat.id
            )
            .count()
        )

    return render_template(
        'admin_categories.html',
        categories=categories,
        category_usage=category_usage,
    )


# =========================================================
# VIEWERS & TOKENS
# =========================================================

@admin_bp.route('/admin/viewers')
@login_required
@admin_required
def admin_viewers():

    tokens = ApiToken.query.order_by(
        ApiToken.created_at.desc()
    ).all()

    viewers = ActiveViewer.query.order_by(
        ActiveViewer.last_seen.desc()
    ).all()

    return render_template(
        'admin_viewers.html',
        tokens=tokens,
        viewers=viewers,
    )


# =========================================================
# REVOKE TOKEN
# =========================================================

@admin_bp.route(
    '/admin/viewers/revoke_token',
    methods=['POST']
)
@login_required
@admin_required
def revoke_token():

    token_id = request.form.get(
        'token_id'
    )

    if not token_id:

        flash(
            'Token id required'
        )

        return redirect(
            url_for('admin.admin_viewers')
        )

    try:

        token = ApiToken.query.get(
            int(token_id)
        )

    except (ValueError, TypeError):

        token = None

    if not token:

        flash(
            'Token not found'
        )

        return redirect(
            url_for('admin.admin_viewers')
        )

    try:

        db.session.delete(token)
        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            'Could not revoke token.'
        )

        return redirect(
            url_for('admin.admin_viewers')
        )

    flash(
        'Token revoked'
    )

    return redirect(
        url_for('admin.admin_viewers')
    )


# =========================================================
# REMOVE ACTIVE VIEWER
# =========================================================

@admin_bp.route(
    '/admin/viewers/remove_viewer',
    methods=['POST']
)
@login_required
@admin_required
def remove_viewer():

    client_id = request.form.get(
        'client_id'
    )

    page = request.form.get(
        'page'
    )

    if not client_id or not page:

        flash(
            'client_id and page required'
        )

        return redirect(
            url_for('admin.admin_viewers')
        )

    try:

        (
            ActiveViewer.query
            .filter_by(
                client_id=client_id,
                page=page,
            )
            .delete()
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            'Could not remove viewer.'
        )

        return redirect(
            url_for('admin.admin_viewers')
        )

    flash(
        'Viewer entry removed'
    )

    return redirect(
        url_for('admin.admin_viewers')
    )
