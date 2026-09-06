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
    db,
    Suggestion,
    User,
    ApiToken,
    ActiveViewer,
)


admin_bp = Blueprint("admin", __name__)


# =========================================================
# HELPERS
# =========================================================

def normalize_poem_text(value):
    return " ".join((value or "").strip().split()).lower()


def admin_required(f):

    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):

        if not current_user.is_authenticated:
            flash("Login required to manage poems.")
            return redirect(url_for("auth.login"))

        if not getattr(current_user, "is_admin", False):
            flash("Admin access required.")
            return redirect(url_for("index"))

        return f(*args, **kwargs)

    return wrapped


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route("/admin")
@login_required
@admin_required
def admin_index():

    # -----------------------------------------------------
    # Poems
    # -----------------------------------------------------

    try:
        poems = (
            Poem.query
            .order_by(Poem.created_at.desc())
            .all()
        )
    except Exception:
        db.session.rollback()
        poems = []


    # -----------------------------------------------------
    # Categories
    # -----------------------------------------------------

    try:
        categories = Category.query.all()
    except Exception:
        db.session.rollback()
        categories = []


    # -----------------------------------------------------
    # Users
    # -----------------------------------------------------

    try:
        users = (
            User.query
            .order_by(User.created_at.desc())
            .all()
        )
    except Exception:
        db.session.rollback()
        users = []


    # -----------------------------------------------------
    # Suggestions
    # -----------------------------------------------------

    try:
        suggestions = (
            Suggestion.query
            .order_by(Suggestion.created_at.desc())
            .all()
        )
    except Exception:
        db.session.rollback()
        suggestions = []


    # -----------------------------------------------------
    # Published poems count
    # -----------------------------------------------------

    try:
        total_poems = (
            Poem.query
            .filter_by(published=True)
            .count()
        )
    except Exception:
        db.session.rollback()
        total_poems = 0


    # -----------------------------------------------------
    # Favorites count
    # -----------------------------------------------------

    try:
        total_favorites = Favorite.query.count()
    except Exception:
        db.session.rollback()
        total_favorites = 0


    # -----------------------------------------------------
    # Render dashboard
    # -----------------------------------------------------

    return render_template(
        "admin.html",
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

@admin_bp.route(
    "/admin/poem/new",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def admin_new_poem():

    try:
        categories = Category.query.all()
    except Exception:
        db.session.rollback()
        categories = []


    if request.method == "POST":

        # -------------------------------------------------
        # JSON / Offline sync
        # -------------------------------------------------

        if request.is_json:

            payload = request.get_json() or {}

            title = (
                payload.get("title") or ""
            ).strip()

            body = (
                payload.get("body") or ""
            ).strip()

            description = (
                payload.get("description") or ""
            ).strip()

            category_id = payload.get(
                "category_id"
            )

            tags = (
                payload.get("tags") or ""
            ).strip()

        # -------------------------------------------------
        # Normal browser form
        # -------------------------------------------------

        else:

            title = (
                request.form.get("title") or ""
            ).strip()

            body = (
                request.form.get("body") or ""
            ).strip()

            description = (
                request.form.get("description") or ""
            ).strip()

            category_id = request.form.get(
                "category_id"
            )

            tags = (
                request.form.get("tags") or ""
            ).strip()


        # -------------------------------------------------
        # Validation
        # -------------------------------------------------

        if not title or not body:

            if request.is_json:
                return jsonify({
                    "error": "Title and body required"
                }), 400

            flash(
                "Please add both a title and the poem text."
            )

            return redirect(
                url_for("admin.admin_new_poem")
            )


        # -------------------------------------------------
        # Duplicate check
        # -------------------------------------------------

        normalized_title = normalize_poem_text(title)
        normalized_body = normalize_poem_text(body)

        try:

            published_poems = (
                Poem.query
                .filter_by(published=True)
                .all()
            )

        except Exception:

            db.session.rollback()
            published_poems = []


        for poem in published_poems:

            if (
                normalize_poem_text(poem.title)
                == normalized_title
                and
                normalize_poem_text(poem.body)
                == normalized_body
            ):

                message = (
                    "This poem already exists in the library "
                    "and was not added again."
                )

                if request.is_json:

                    return jsonify({
                        "ok": False,
                        "error": "duplicate",
                        "message": message
                    }), 409

                flash(message)

                return redirect(
                    url_for("admin.admin_new_poem")
                )


        # -------------------------------------------------
        # Category
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
        # Create poem
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
        # Cover image
        # -------------------------------------------------

        if not request.is_json:

            image_file = request.files.get(
                "cover_image"
            )

            if (
                image_file
                and image_file.filename
            ):

                allowed = {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".gif",
                }

                ext = os.path.splitext(
                    image_file.filename
                )[1].lower()

                if ext in allowed:

                    upload_dir = os.path.join(
                        current_app.static_folder,
                        "img",
                        "covers"
                    )

                    os.makedirs(
                        upload_dir,
                        exist_ok=True
                    )

                    db.session.flush()

                    safe_title = (
                        title
                        .lower()
                        .replace(" ", "-")
                    )

                    filename = secure_filename(
                        f"{safe_title}-{poem.id}{ext}"
                    )

                    image_path = os.path.join(
                        upload_dir,
                        filename
                    )

                    image_file.save(
                        image_path
                    )

                    poem.cover_image = (
                        f"/static/img/covers/{filename}"
                    )


        # -------------------------------------------------
        # Save
        # -------------------------------------------------

        try:

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            if request.is_json:

                return jsonify({
                    "ok": False,
                    "error": str(e)
                }), 500

            flash(
                "Unable to save the poem. Please try again."
            )

            return redirect(
                url_for("admin.admin_index")
            )


        if request.is_json:

            return jsonify({
                "ok": True,
                "title": title,
                "id": poem.id,
                "message": "Poem saved successfully."
            })


        flash(
            "Your poem has found its place in "
            f"Moonlit Marginalia: {title}"
        )

        return redirect(
            url_for("admin.admin_index")
        )


    return render_template(
        "admin_new_poem.html",
        categories=categories
    )


# =========================================================
# EDIT POEM
# =========================================================

@admin_bp.route(
    "/admin/poem/<int:poem_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def admin_edit_poem(poem_id):

    try:

        poem = Poem.query.get(poem_id)

    except Exception:

        db.session.rollback()
        poem = None


    if poem is None:

        flash("Poem not found.")

        return redirect(
            url_for("admin.admin_index")
        )


    try:

        categories = Category.query.all()

    except Exception:

        db.session.rollback()
        categories = []


    if request.method == "POST":

        title = (
            request.form.get("title") or ""
        ).strip()

        body = (
            request.form.get("body") or ""
        ).strip()

        description = (
            request.form.get("description") or ""
        ).strip()

        category_id = request.form.get(
            "category_id"
        )

        tags = (
            request.form.get("tags") or ""
        ).strip()


        # -------------------------------------------------
        # Validation
        # -------------------------------------------------

        if not title or not body:

            flash(
                "Please add both a title and the poem text."
            )

            return redirect(
                url_for(
                    "admin.admin_edit_poem",
                    poem_id=poem_id
                )
            )


        # -------------------------------------------------
        # Duplicate check
        # -------------------------------------------------

        normalized_title = normalize_poem_text(title)
        normalized_body = normalize_poem_text(body)

        try:

            other_poems = (
                Poem.query
                .filter_by(published=True)
                .all()
            )

        except Exception:

            db.session.rollback()
            other_poems = []


        for other_poem in other_poems:

            if other_poem.id == poem_id:
                continue

            if (
                normalize_poem_text(
                    other_poem.title
                )
                == normalized_title
                and
                normalize_poem_text(
                    other_poem.body
                )
                == normalized_body
            ):

                flash(
                    "A poem with this title and "
                    "text already exists."
                )

                return redirect(
                    url_for(
                        "admin.admin_edit_poem",
                        poem_id=poem_id
                    )
                )


        # -------------------------------------------------
        # Update
        # -------------------------------------------------

        poem.title = title
        poem.body = body
        poem.description = (
            description or None
        )
        poem.tags = tags or None


        # -------------------------------------------------
        # Category
        # -------------------------------------------------

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
        # Cover
        # -------------------------------------------------

        image_file = request.files.get(
            "cover_image"
        )

        if (
            image_file
            and image_file.filename
        ):

            allowed = {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".gif",
            }

            ext = os.path.splitext(
                image_file.filename
            )[1].lower()

            if ext in allowed:

                upload_dir = os.path.join(
                    current_app.static_folder,
                    "img",
                    "covers"
                )

                os.makedirs(
                    upload_dir,
                    exist_ok=True
                )

                filename = secure_filename(
                    f"{title.lower().replace(' ', '-')}"
                    f"-{poem_id}{ext}"
                )

                image_file.save(
                    os.path.join(
                        upload_dir,
                        filename
                    )
                )

                poem.cover_image = (
                    f"/static/img/covers/{filename}"
                )


        # -------------------------------------------------
        # Commit
        # -------------------------------------------------

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update the poem."
            )

            return redirect(
                url_for(
                    "admin.admin_edit_poem",
                    poem_id=poem_id
                )
            )


        flash(
            f"Poem updated: {title}"
        )

        return redirect(
            url_for("admin.admin_index")
        )


    return render_template(
        "admin_edit_poem.html",
        poem=poem,
        categories=categories,
    )


# =========================================================
# DELETE POEM
# =========================================================

@admin_bp.route(
    "/admin/poem/<int:poem_id>/delete",
    methods=["POST"]
)
@login_required
@admin_required
def admin_delete_poem(poem_id):

    try:

        poem = Poem.query.get(poem_id)

    except Exception:

        db.session.rollback()
        poem = None


    if poem is None:

        flash("Poem not found.")

        return redirect(
            url_for("admin.admin_index")
        )


    title = poem.title

    try:

        db.session.delete(poem)
        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to delete the poem."
        )

        return redirect(
            url_for("admin.admin_index")
        )


    flash(
        f"Poem removed from the collection: {title}"
    )

    return redirect(
        url_for("admin.admin_index")
    )


# =========================================================
# FEATURE / UNFEATURE
# =========================================================

@admin_bp.route(
    "/admin/poem/<int:poem_id>/feature",
    methods=["POST"]
)
@login_required
@admin_required
def admin_feature_poem(poem_id):

    try:

        poem = Poem.query.get(poem_id)

    except Exception:

        db.session.rollback()
        poem = None


    if poem is None:

        return jsonify({
            "error": "Poem not found"
        }), 404


    try:

        Poem.query.filter(
            Poem.id != poem_id
        ).update({
            "is_featured": False
        })

        poem.is_featured = not poem.is_featured

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 500


    return jsonify({
        "success": True,
        "is_featured": poem.is_featured,
        "message": (
            "Featured status: "
            f"{'On' if poem.is_featured else 'Off'}"
        ),
    })


# =========================================================
# CATEGORY MANAGEMENT
# =========================================================

@admin_bp.route(
    "/admin/categories",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def admin_categories():

    if request.method == "POST":

        action = request.form.get(
            "action"
        )


        # -------------------------------------------------
        # ADD
        # -------------------------------------------------

        if action == "add":

            name = (
                request.form.get("name") or ""
            ).strip()

            if not name:

                flash(
                    "Category name required."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
                    )
                )


            try:

                existing = (
                    Category.query
                    .filter_by(name=name)
                    .first()
                )

            except Exception:

                db.session.rollback()
                existing = None


            if existing:

                flash(
                    "Category already exists."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
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
                    "Unable to add category."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
                    )
                )


            flash(
                f"Category added: {name}"
            )


        # -------------------------------------------------
        # DELETE
        # -------------------------------------------------

        elif action == "delete":

            category_id = request.form.get(
                "category_id"
            )

            try:

                category = Category.query.get(
                    int(category_id)
                )

            except (ValueError, TypeError):

                category = None

            except Exception:

                db.session.rollback()
                category = None


            if category is None:

                flash(
                    "Category not found."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
                    )
                )


            try:

                poems_using = (
                    Poem.query
                    .filter_by(
                        category_id=category.id
                    )
                    .count()
                )

            except Exception:

                db.session.rollback()
                poems_using = 0


            if poems_using > 0:

                flash(
                    "Cannot delete category in use by "
                    f"{poems_using} poem(s)."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
                    )
                )


            category_name = category.name

            db.session.delete(category)

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                flash(
                    "Unable to delete category."
                )

                return redirect(
                    url_for(
                        "admin.admin_categories"
                    )
                )


            flash(
                f"Category deleted: {category_name}"
            )


        return redirect(
            url_for("admin.admin_categories")
        )


    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    try:

        categories = Category.query.all()

    except Exception:

        db.session.rollback()
        categories = []


    category_usage = {}


    for cat in categories:

        try:

            category_usage[cat.id] = (
                Poem.query
                .filter_by(
                    category_id=cat.id
                )
                .count()
            )

        except Exception:

            db.session.rollback()
            category_usage[cat.id] = 0


    return render_template(
        "admin_categories.html",
        categories=categories,
        category_usage=category_usage,
    )


# =========================================================
# ADMIN VIEWERS
# =========================================================

@admin_bp.route("/admin/viewers")
@login_required
@admin_required
def admin_viewers():

    try:

        tokens = (
            ApiToken.query
            .order_by(
                ApiToken.created_at.desc()
            )
            .all()
        )

    except Exception:

        db.session.rollback()
        tokens = []


    try:

        viewers = (
            ActiveViewer.query
            .order_by(
                ActiveViewer.last_seen.desc()
            )
            .all()
        )

    except Exception:

        db.session.rollback()
        viewers = []


    return render_template(
        "admin_viewers.html",
        tokens=tokens,
        viewers=viewers
    )


# =========================================================
# REVOKE API TOKEN
# =========================================================

@admin_bp.route(
    "/admin/viewers/revoke_token",
    methods=["POST"]
)
@login_required
@admin_required
def revoke_token():

    token_id = request.form.get(
        "token_id"
    )

    if not token_id:

        flash(
            "Token id required"
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    try:

        token_id = int(token_id)

    except (ValueError, TypeError):

        flash(
            "Invalid token id"
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    try:

        token = ApiToken.query.get(
            token_id
        )

    except Exception:

        db.session.rollback()
        token = None


    if not token:

        flash(
            "Token not found"
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    try:

        db.session.delete(token)
        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to revoke token."
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    flash(
        "Token revoked"
    )

    return redirect(
        url_for("admin.admin_viewers")
    )


# =========================================================
# REMOVE ACTIVE VIEWER
# =========================================================

@admin_bp.route(
    "/admin/viewers/remove_viewer",
    methods=["POST"]
)
@login_required
@admin_required
def remove_viewer():

    client_id = (
        request.form.get("client_id") or ""
    ).strip()

    page = (
        request.form.get("page") or ""
    ).strip()


    if not client_id or not page:

        flash(
            "client_id and page required"
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    try:

        (
            ActiveViewer.query
            .filter_by(
                client_id=client_id,
                page=page
            )
            .delete()
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to remove viewer."
        )

        return redirect(
            url_for("admin.admin_viewers")
        )


    flash(
        "Viewer entry removed"
    )

    return redirect(
        url_for("admin.admin_viewers")
    )
