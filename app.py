import os
from datetime import datetime
import click

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from flask_login import (
    LoginManager,
    login_required,
    current_user,
)

from models import db


def create_app():

    # =========================================================
    # FLASK APP
    # =========================================================

    app = Flask(
        __name__,
        instance_relative_config=True
    )

    try:
        os.makedirs(
            app.instance_path,
            exist_ok=True
        )
    except Exception:
        pass

    # =========================================================
    # SECRET KEY
    # =========================================================

    secret_file = os.path.join(
        app.instance_path,
        "secret_key"
    )

    secret_key = os.environ.get(
        "SECRET_KEY"
    )

    if not secret_key:

        try:
            if os.path.exists(secret_file):

                with open(
                    secret_file,
                    "rb"
                ) as fh:

                    secret_key = (
                        fh.read()
                        .decode("utf-8")
                    )

            else:

                secret_key = (
                    os.urandom(24)
                    .hex()
                )

                with open(
                    secret_file,
                    "wb"
                ) as fh:

                    fh.write(
                        secret_key.encode("utf-8")
                    )

        except Exception:

            secret_key = "dev-secret"

    app.config["SECRET_KEY"] = secret_key

    app.config["ADMIN_USERNAME"] = (
        os.environ.get(
            "ADMIN_USERNAME",
            "admin"
        )
    )

    app.config["ADMIN_PASSWORD"] = (
        os.environ.get(
            "ADMIN_PASSWORD",
            "admin123"
        )
    )

    # =========================================================
    # DATABASE
    # =========================================================

    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if not database_url:

        db_path = os.path.join(
            app.instance_path,
            "ink_and_echoes.db"
        )

        database_url = (
            "sqlite:///"
            + os.path.abspath(db_path)
            .replace("\\", "/")
        )

    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = database_url

    if app.config[
        "SQLALCHEMY_DATABASE_URI"
    ].startswith("postgres"):

        app.config[
            "SQLALCHEMY_DATABASE_URI"
        ] = (
            app.config[
                "SQLALCHEMY_DATABASE_URI"
            ].replace(
                "postgres://",
                "postgresql://",
                1
            )
        )

    app.config[
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    ] = False

    app.config["DEBUG"] = (
        os.environ.get(
            "FLASK_DEBUG",
            "0"
        ) == "1"
    )

    db.init_app(app)

    # =========================================================
    # LOGIN MANAGER
    # =========================================================

    login_manager = LoginManager()

    login_manager.login_view = "auth.login"

    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):

        try:

            # Clear any previously failed transaction
            db.session.rollback()

            return User.query.get(
                int(user_id)
            )

        except Exception:

            db.session.rollback()

            return None

    # =========================================================
    # BLUEPRINTS
    # =========================================================

    from auth import auth_bp

    app.register_blueprint(
        auth_bp
    )

    from admin import admin_bp

    app.register_blueprint(
        admin_bp
    )

    from ai import ai_bp

    app.register_blueprint(
        ai_bp
    )

    # =========================================================
    # GLOBAL SITE STATISTICS
    # =========================================================

    @app.context_processor
    def inject_site_stats():

        from models import (
            User,
            Poem,
            Category,
            Favorite,
            PageView,
        )

        # -------------------------
        # TOTAL POEMS
        # -------------------------

        try:

            total_poems = (
                Poem.query
                .filter_by(
                    published=True
                )
                .count()
            )

        except Exception:

            db.session.rollback()

            total_poems = 0

        # -------------------------
        # REGISTERED USERS
        # -------------------------

        try:

            registered_users = (
                User.query.count()
            )

        except Exception:

            db.session.rollback()

            registered_users = 0

        # -------------------------
        # CATEGORIES
        # -------------------------

        try:

            total_categories = (
                Category.query.count()
            )

        except Exception:

            db.session.rollback()

            total_categories = 0

        # -------------------------
        # FAVORITES
        # -------------------------

        try:

            total_favorites = (
                Favorite.query.count()
            )

        except Exception:

            db.session.rollback()

            total_favorites = 0

        # -------------------------
        # TOTAL VIEWS
        # -------------------------

        try:

            total_views = (
                db.session.query(
                    db.func.coalesce(
                        db.func.sum(
                            PageView.count
                        ),
                        0
                    )
                ).scalar()
                or 0
            )

        except Exception:

            db.session.rollback()

            total_views = 0

        return {

            "poems_total_views":
                total_views,

            "total_poems":
                total_poems,

            "total_categories":
                total_categories,

            "total_favorites":
                total_favorites,

            "registered_users":
                registered_users,

            "total_views":
                total_views,
        }

    # =========================================================
    # INIT DATABASE
    # =========================================================

    @app.cli.command("init-db")
    def init_db():

        """Initialize the database."""

        from models import db as _db

        try:

            _db.create_all()

            try:

                from auth import get_admin_user

                get_admin_user()

            except Exception:

                _db.session.rollback()

            print(
                "Database initialized and admin user ensured."
            )

        except Exception as e:

            _db.session.rollback()

            print(
                f"Database initialization failed: {e}"
            )

    # =========================================================
    # CREATE ADMIN
    # =========================================================

    @app.cli.command("create-admin")

    @click.option(
        "--username",
        "-u",
        required=True
    )

    @click.option(
        "--password",
        "-p",
        required=True
    )

    def create_admin(
        username,
        password
    ):

        from models import (
            User,
            db as _db
        )

        try:

            user = (
                User.query
                .filter_by(
                    username=username
                )
                .first()
            )

            if user is None:

                user = User(
                    username=username,
                    email=f"{username}@admin.local",
                    is_admin=True
                )

                user.set_password(
                    password
                )

                _db.session.add(
                    user
                )

                _db.session.commit()

                print(
                    f"Created admin user: {username}"
                )

            else:

                user.is_admin = True

                user.set_password(
                    password
                )

                _db.session.commit()

                print(
                    f"Updated admin user: {username}"
                )

        except Exception as e:

            _db.session.rollback()

            print(
                f"Failed to create admin: {e}"
            )

    # =========================================================
    # CREATE API TOKEN
    # =========================================================

    @app.cli.command("create-token")

    @click.option(
        "--username",
        "-u",
        required=True
    )

    @click.option(
        "--name",
        "-n",
        required=False
    )

    def create_token(
        username,
        name
    ):

        from models import (
            User,
            ApiToken,
            db as _db
        )

        import secrets

        try:

            user = (
                User.query
                .filter(
                    (
                        User.username
                        == username
                    )
                    |
                    (
                        User.email
                        == username
                    )
                )
                .first()
            )

            if not user or not getattr(
                user,
                "is_admin",
                False
            ):

                print(
                    "User not found or not an admin"
                )

                return

            raw = secrets.token_urlsafe(
                32
            )

            token_hash = (
                generate_password_hash(
                    raw
                )
            )

            token = ApiToken(
                user_id=user.id,
                name=name,
                token_hash=token_hash
            )

            _db.session.add(
                token
            )

            _db.session.commit()

            print(
                "Created token for",
                username
            )

            print(
                "Raw token (store this somewhere safe):"
            )

            print(raw)

        except Exception as e:

            _db.session.rollback()

            print(
                f"Failed to create token: {e}"
            )

    # =========================================================
    # BACKUP DATABASE
    # =========================================================

    @app.cli.command("backup-db")
    def backup_db_cli():

        import shutil
        import datetime as dt

        src = os.path.join(
            app.instance_path,
            "ink_and_echoes.db"
        )

        if not os.path.exists(src):

            print(
                "No database file to backup:",
                src
            )

            return

        backups_dir = os.path.join(
            app.instance_path,
            "backups"
        )

        os.makedirs(
            backups_dir,
            exist_ok=True
        )

        ts = (
            dt.datetime
            .utcnow()
            .strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )

        dst = os.path.join(
            backups_dir,
            f"ink_and_echoes-{ts}.db"
        )

        shutil.copy2(
            src,
            dst
        )

        print(
            "Backed up DB to",
            dst
        )

    # =========================================================
    # HOME
    # =========================================================

    @app.route("/")
    def index():

        from models import (
            Poem,
            PageView,
            Category
        )

        try:

            page_view = (
                PageView.query
                .filter_by(
                    page="home"
                )
                .first()
            )

            if page_view is None:

                page_view = PageView(
                    page="home",
                    count=1
                )

                db.session.add(
                    page_view
                )

            else:

                page_view.count += 1

            db.session.commit()

        except Exception:

            db.session.rollback()

        poems = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .limit(3)
            .all()
        )

        recent_poem_ids = {

            poem.id

            for poem in poems

            if (
                poem.created_at
                and
                (
                    datetime.utcnow()
                    - poem.created_at
                ).days <= 7
            )
        }

        latest_poem = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .first()
        )

        has_new_poem = bool(

            latest_poem

            and latest_poem.created_at

            and (
                datetime.utcnow()
                - latest_poem.created_at
            ).days <= 7
        )

        featured_poem = (
            Poem.query
            .filter_by(
                published=True,
                is_featured=True
            )
            .first()
        )

        if featured_poem is None:

            featured_poem = latest_poem

        categories = (
            Category.query.all()
        )

        return render_template(

            "index.html",

            poems=poems,

            recent_poem_ids=
                recent_poem_ids,

            latest_poem=
                latest_poem,

            has_new_poem=
                has_new_poem,

            featured_poem=
                featured_poem,

            categories=
                categories,
        )

    # =========================================================
    # POEMS
    # =========================================================

    @app.route("/poems")
    def poems():

        from models import (
            Poem,
            PageView,
            Category,
        )

        try:

            page_view = (
                PageView.query
                .filter_by(
                    page="poems"
                )
                .first()
            )

            if page_view is None:

                page_view = PageView(
                    page="poems",
                    count=1
                )

                db.session.add(
                    page_view
                )

            else:

                page_view.count += 1

            db.session.commit()

        except Exception:

            db.session.rollback()

        category_filter = (
            request.args
            .get(
                "category",
                ""
            )
            .strip()
        )

        search_query = (
            request.args
            .get(
                "search",
                ""
            )
            .strip()
        )

        sort_by = (
            request.args
            .get(
                "sort",
                "newest"
            )
        )

        query = (
            Poem.query
            .filter_by(
                published=True
            )
        )

        if (
            category_filter
            and
            category_filter != "all"
        ):

            try:

                query = (
                    query.filter_by(
                        category_id=
                            int(category_filter)
                    )
                )

            except ValueError:

                pass

        if search_query:

            search_pattern = (
                f"%{search_query}%"
            )

            query = query.filter(

                (
                    Poem.title
                    .ilike(
                        search_pattern
                    )
                )

                |

                (
                    Poem.body
                    .ilike(
                        search_pattern
                    )
                )

                |

                (
                    Poem.description
                    .ilike(
                        search_pattern
                    )
                )
            )

        if sort_by == "oldest":

            query = (
                query.order_by(
                    Poem.created_at.asc()
                )
            )

        elif sort_by == "a-z":

            query = (
                query.order_by(
                    Poem.title.asc()
                )
            )

        else:

            query = (
                query.order_by(
                    Poem.created_at.desc()
                )
            )

        poems = query.all()

        categories = (
            Category.query.all()
        )

        user_favorites = []

        if current_user.is_authenticated:

            from models import Favorite

            try:

                user_favorites = [

                    fav.poem_id

                    for fav in (
                        Favorite.query
                        .filter_by(
                            user_id=
                                current_user.id
                        )
                        .all()
                    )
                ]

            except Exception:

                db.session.rollback()

                user_favorites = []

        return render_template(

            "poems.html",

            poems=poems,

            categories=categories,

            user_favorites=
                user_favorites,

            current_sort=
                sort_by,

            current_search=
                search_query,

            current_category=
                category_filter,
        )

    # =========================================================
    # FULL POEMS
    # =========================================================

    @app.route("/poems/full")
    def poems_full():

        from models import Poem

        poems = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .all()
        )

        return render_template(

            "poems.html",

            poems=poems,

            require_login=False,

            full_view=True,
        )

    # =========================================================
    # POEM DETAIL
    # =========================================================

    @app.route("/poem/<int:poem_id>")
    def poem_detail(
        poem_id
    ):

        from models import (
            Poem,
            Favorite,
            History,
        )

        poem = Poem.query.get(
            poem_id
        )

        if (
            poem is None
            or not poem.published
        ):

            flash(
                "This verse seems to have wandered beyond the margins."
            )

            return redirect(
                url_for("poems")
            )

        if current_user.is_authenticated:

            try:

                history = History(

                    user_id=
                        current_user.id,

                    poem_id=
                        poem_id,
                )

                db.session.add(
                    history
                )

                db.session.commit()

            except Exception:

                db.session.rollback()

        is_favorited = False

        if current_user.is_authenticated:

            try:

                favorite = (
                    Favorite.query
                    .filter_by(
                        user_id=
                            current_user.id,

                        poem_id=
                            poem_id,
                    )
                    .first()
                )

                is_favorited = (
                    favorite is not None
                )

            except Exception:

                db.session.rollback()

                is_favorited = False

        all_poems = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .all()
        )

        poem_ids = [
            p.id
            for p in all_poems
        ]

        current_index = (

            poem_ids.index(poem_id)

            if poem_id in poem_ids

            else -1
        )

        prev_poem = (

            all_poems[
                current_index - 1
            ]

            if current_index > 0

            else None
        )

        next_poem = (

            all_poems[
                current_index + 1
            ]

            if (
                current_index >= 0
                and
                current_index
                <
                len(all_poems) - 1
            )

            else None
        )

        return render_template(

            "poem_detail.html",

            poem=poem,

            is_favorited=
                is_favorited,

            prev_poem=
                prev_poem,

            next_poem=
                next_poem,
        )

    # =========================================================
    # FAVORITES
    # =========================================================

    @app.route("/favorites")
    @login_required
    def favorites():

        from models import (
            Poem,
            Favorite
        )

        try:

            favorites = (
                Favorite.query
                .filter_by(
                    user_id=
                        current_user.id
                )
                .order_by(
                    Favorite.created_at.desc()
                )
                .all()
            )

        except Exception:

            db.session.rollback()

            favorites = []

        favorite_poems = []

        for fav in favorites:

            try:

                poem = Poem.query.get(
                    fav.poem_id
                )

                if (
                    poem
                    and
                    poem.published
                ):

                    favorite_poems.append(
                        poem
                    )

            except Exception:

                db.session.rollback()

        return render_template(

            "favorites.html",

            poems=favorite_poems,

            total_favorites=
                len(favorite_poems),
        )

    # =========================================================
    # FAVORITE API
    # =========================================================

    @app.route(
        "/api/v1/favorite/<int:poem_id>",
        methods=["POST"]
    )
    @login_required
    def api_favorite_poem(
        poem_id
    ):

        from models import (
            Poem,
            Favorite
        )

        poem = Poem.query.get(
            poem_id
        )

        if (
            poem is None
            or not poem.published
        ):

            return jsonify({
                "error":
                    "Poem not found"
            }), 404

        try:

            existing_favorite = (
                Favorite.query
                .filter_by(
                    user_id=
                        current_user.id,

                    poem_id=
                        poem_id,
                )
                .first()
            )

        except Exception:

            db.session.rollback()

            return jsonify({

                "error":
                    "Favorites database is not ready yet."

            }), 500

        if existing_favorite:

            try:

                db.session.delete(
                    existing_favorite
                )

                db.session.commit()

            except Exception as e:

                db.session.rollback()

                return jsonify({
                    "error": str(e)
                }), 500

            return jsonify({

                "success":
                    True,

                "favorited":
                    False,

                "message":
                    "Removed from favorites"
            })

        else:

            try:

                new_favorite = Favorite(

                    user_id=
                        current_user.id,

                    poem_id=
                        poem_id,
                )

                db.session.add(
                    new_favorite
                )

                db.session.commit()

            except Exception as e:

                db.session.rollback()

                return jsonify({
                    "error": str(e)
                }), 500

            return jsonify({

                "success":
                    True,

                "favorited":
                    True,

                "message":
                    "Added to favorites"
            })

    # =========================================================
    # AI COMPANION
    # =========================================================

    @app.route("/chat")
    def chat():

        return render_template(
            "chat.html"
        )

    # =========================================================
    # POEMS API
    # =========================================================

    @app.route(
        "/api/v1/poems"
    )
    def api_poems():

        from models import (
            Poem,
            Category
        )

        poems = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .all()
        )

        output = []

        for poem in poems:

            category_name = None

            if poem.category_id:

                category = (
                    Category.query.get(
                        poem.category_id
                    )
                )

                if category:

                    category_name = (
                        category.name
                    )

            output.append({

                "id":
                    poem.id,

                "title":
                    poem.title,

                "body":
                    poem.body,

                "description":
                    getattr(
                        poem,
                        "description",
                        None
                    ),

                "category":
                    category_name,

                "created_at":
                    (
                        poem.created_at.isoformat()
                        if poem.created_at
                        else None
                    ),
            })

        return jsonify(
            output
        )

    # =========================================================
    # NOTIFICATIONS API
    # =========================================================

    @app.route(
        "/api/v1/notifications"
    )
    def api_notifications():

        from models import Poem

        poems = (
            Poem.query
            .filter_by(
                published=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .limit(10)
            .all()
        )

        return jsonify([

            {

                "id":
                    poem.id,

                "title":
                    poem.title,

                "created_at":
                    (
                        poem.created_at.isoformat()
                        if poem.created_at
                        else None
                    ),

                "url":
                    url_for("poems"),
            }

            for poem in poems
        ])

    # =========================================================
    # SINGLE POEM API
    # =========================================================

    @app.route(
        "/api/v1/poems/<int:poem_id>"
    )
    def api_poem_detail(
        poem_id
    ):

        from models import (
            Poem,
            Category
        )

        poem = Poem.query.get(
            poem_id
        )

        if (
            poem is None
            or not poem.published
        ):

            return jsonify({

                "error":
                    "not found"

            }), 404

        category_name = None

        if poem.category_id:

            category = (
                Category.query.get(
                    poem.category_id
                )
            )

            if category:

                category_name = (
                    category.name
                )

        return jsonify({

            "id":
                poem.id,

            "title":
                poem.title,

            "body":
                poem.body,

            "description":
                getattr(
                    poem,
                    "description",
                    None
                ),

            "category":
                category_name,

            "created_at":
                (
                    poem.created_at.isoformat()
                    if poem.created_at
                    else None
                ),
        })

    # =========================================================
    # ADMIN REQUEST CHECK
    # =========================================================

    def _is_admin_request():

        try:

            if (

                getattr(
                    current_user,
                    "is_authenticated",
                    False
                )

                and

                getattr(
                    current_user,
                    "is_admin",
                    False
                )

            ):

                return True

        except Exception:

            db.session.rollback()

        # X-API-KEY

        api_key = request.headers.get(
            "X-API-KEY"
        )

        if (

            api_key

            and

            api_key
            ==
            app.config.get(
                "SECRET_KEY"
            )

        ):

            return True

        # Basic authentication

        auth = request.headers.get(
            "Authorization"
        )

        if (
            auth
            and
            auth.startswith("Basic ")
        ):

            try:

                import base64

                from models import User

                encoded = (
                    auth.split(
                        " ",
                        1
                    )[1]
                )

                credentials = (
                    base64.b64decode(
                        encoded
                    )
                    .decode("utf-8")
                )

                username, password = (
                    credentials.split(
                        ":",
                        1
                    )
                )

                user = (
                    User.query
                    .filter(
                        (
                            User.username
                            ==
                            username
                        )
                        |
                        (
                            User.email
                            ==
                            username
                        )
                    )
                    .first()
                )

                if (

                    user

                    and

                    user.check_password(
                        password
                    )

                    and

                    getattr(
                        user,
                        "is_admin",
                        False
                    )

                ):

                    return True

            except Exception:

                db.session.rollback()

        # Bearer token

        if (
            auth
            and
            auth.startswith("Bearer ")
        ):

            try:

                token = (
                    auth.split(
                        " ",
                        1
                    )[1]
                )

                from models import ApiToken

                for api_token in (
                    ApiToken.query.all()
                ):

                    if (

                        check_password_hash(
                            api_token.token_hash,
                            token
                        )

                        and

                        getattr(
                            api_token.user,
                            "is_admin",
                            False
                        )

                    ):

                        return True

            except Exception:

                db.session.rollback()

        return False

    # =========================================================
    # CREATE POEM API
    # =========================================================

    @app.route(
        "/api/v1/poems",
        methods=["POST"]
    )
    def api_poems_create():

        if not _is_admin_request():

            return jsonify({

                "error":
                    "unauthorized"

            }), 401

        if not request.is_json:

            return jsonify({

                "error":
                    "expected JSON body"

            }), 400

        payload = (
            request.get_json()
        )

        title = (
            payload.get("title")
            or ""
        ).strip()

        body = (
            payload.get("body")
            or ""
        ).strip()

        category_name = (
            payload.get("category")
            or ""
        ).strip()

        published = bool(
            payload.get(
                "published",
                True
            )
        )

        if not title or not body:

            return jsonify({

                "error":
                    "title and body required"

            }), 400

        from models import (
            Poem,
            Category,
            db as _db
        )

        def normalize_text(
            text
        ):

            return (
                " "
                .join(
                    (
                        text
                        or ""
                    )
                    .strip()
                    .split()
                )
                .lower()
            )

        try:

            normalized_title = (
                normalize_text(
                    title
                )
            )

            normalized_body = (
                normalize_text(
                    body
                )
            )

            for poem in (
                Poem.query
                .filter_by(
                    published=True
                )
                .all()
            ):

                if (

                    normalize_text(
                        poem.title
                    )
                    ==
                    normalized_title

                    and

                    normalize_text(
                        poem.body
                    )
                    ==
                    normalized_body

                ):

                    return jsonify({

                        "ok":
                            False,

                        "error":
                            "duplicate"

                    }), 409

            category = None

            if category_name:

                category = (
                    Category.query
                    .filter_by(
                        name=category_name
                    )
                    .first()
                )

                if not category:

                    category = Category(
                        name=category_name
                    )

                    _db.session.add(
                        category
                    )

                    _db.session.flush()

            poem = Poem(

                title=
                    title,

                body=
                    body,

                category_id=
                    (
                        category.id
                        if category
                        else None
                    ),

                published=
                    published,
            )

            _db.session.add(
                poem
            )

            _db.session.commit()

            return jsonify({

                "ok":
                    True,

                "id":
                    poem.id,

                "title":
                    poem.title
            })

        except Exception as e:

            _db.session.rollback()

            return jsonify({

                "ok":
                    False,

                "error":
                    str(e)

            }), 500

    # =========================================================
    # ACTIVE VIEWERS — PING
    # =========================================================

    @app.route(
        "/api/v1/viewers/ping",
        methods=["POST"]
    )
    def api_viewers_ping():

        if not request.is_json:

            return jsonify({

                "error":
                    "expected JSON"

            }), 400

        payload = (
            request.get_json()
        )

        client_id = (
            payload.get(
                "client_id"
            )
            or ""
        ).strip()

        page = (
            payload.get(
                "page"
            )
            or ""
        ).strip()

        if not client_id or not page:

            return jsonify({

                "error":
                    "client_id and page required"

            }), 400

        from models import (
            ActiveViewer,
            db as _db
        )

        try:

            av = (
                ActiveViewer.query
                .filter_by(
                    client_id=client_id,
                    page=page
                )
                .first()
            )

            if av is None:

                av = ActiveViewer(

                    client_id=
                        client_id,

                    page=
                        page,

                    last_seen=
                        datetime.utcnow(),
                )

                _db.session.add(
                    av
                )

            else:

                av.last_seen = (
                    datetime.utcnow()
                )

            _db.session.commit()

            return jsonify({

                "ok":
                    True
            })

        except Exception as e:

            _db.session.rollback()

            return jsonify({

                "ok":
                    False,

                "error":
                    str(e)

            }), 500

    # =========================================================
    # ACTIVE VIEWERS — COUNT
    # =========================================================

    @app.route(
        "/api/v1/viewers/<page>"
    )
    def api_viewers_count(
        page
    ):

        from models import (
            ActiveViewer
        )

        from datetime import timedelta

        cutoff = (
            datetime.utcnow()
            -
            timedelta(
                seconds=60
            )
        )

        try:

            count = (

                ActiveViewer.query

                .filter(
                    ActiveViewer.page
                    ==
                    page,

                    ActiveViewer.last_seen
                    >=
                    cutoff,
                )

                .count()
            )

        except Exception:

            db.session.rollback()

            count = 0

        return jsonify({

            "count":
                count
        })

    # =========================================================
    # SUGGESTIONS
    # =========================================================

    @app.route(
        "/suggestions",
        methods=["GET", "POST"]
    )
    def suggestions():

        if request.method == "POST":

            from models import (
                Suggestion
            )

            message = (
                request.form
                .get(
                    "message"
                )
                or ""
            ).strip()

            user_id = (

                current_user.id

                if getattr(
                    current_user,
                    "is_authenticated",
                    False
                )

                else None
            )

            if message:

                try:

                    suggestion = Suggestion(

                        user_id=
                            user_id,

                        message=
                            message,
                    )

                    db.session.add(
                        suggestion
                    )

                    db.session.commit()

                    flash(
                        "Your suggestion has been saved to the margins."
                    )

                except Exception:

                    db.session.rollback()

                    flash(
                        "Unable to save your suggestion right now."
                    )

            else:

                flash(
                    "Write a little note before sending it."
                )

            return redirect(
                url_for(
                    "suggestions"
                )
            )

        return render_template(
            "suggestions.html"
        )

    # =========================================================
    # ADMIN SUGGESTIONS
    # =========================================================

    @app.route(
        "/admin/suggestions"
    )
    @login_required
    def admin_suggestions():

        from models import (
            Suggestion,
            User
        )

        if not getattr(
            current_user,
            "is_admin",
            False
        ):

            flash(
                "Admin access required."
            )

            return redirect(
                url_for("index")
            )

        try:

            suggestions = (
                Suggestion.query
                .order_by(
                    Suggestion.created_at.desc()
                )
                .all()
            )

        except Exception:

            db.session.rollback()

            suggestions = []

        results = []

        for suggestion in suggestions:

            try:

                user = (

                    User.query.get(
                        suggestion.user_id
                    )

                    if suggestion.user_id

                    else None
                )

            except Exception:

                db.session.rollback()

                user = None

            results.append({

                "suggestion":
                    suggestion,

                "user":
                    user,
            })

        try:

            users = (
                User.query
                .order_by(
                    User.created_at.desc()
                )
                .all()
            )

        except Exception:

            db.session.rollback()

            users = []

        return render_template(

            "admin_suggestions.html",

            suggestions=
                results,

            users=
                users,
        )

    # =========================================================
    # RETURN APP
    # =========================================================

    return app


# =============================================================
# CREATE APP
# =============================================================

app = create_app()


# =============================================================
# CREATE TABLES
# =============================================================

with app.app_context():

    try:

        db.create_all()

    except Exception:

        db.session.rollback()


# =============================================================
# RUN
# =============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
