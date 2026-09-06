import os
import click
import base64
import secrets
import shutil

from datetime import datetime, timedelta

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from flask_login import (
    LoginManager,
    login_required,
    current_user
)

from models import db


# ============================================================
# APPLICATION FACTORY
# ============================================================

def create_app():

    app = Flask(
        __name__,
        instance_relative_config=True
    )

    # ========================================================
    # INSTANCE FOLDER
    # ========================================================

    try:
        os.makedirs(
            app.instance_path,
            exist_ok=True
        )
    except Exception:
        pass


    # ========================================================
    # SECRET KEY
    # ========================================================

    secret_file = os.path.join(
        app.instance_path,
        "secret_key"
    )

    secret_key = os.environ.get("SECRET_KEY")

    if not secret_key:

        try:

            if os.path.exists(secret_file):

                with open(
                    secret_file,
                    "rb"
                ) as fh:

                    secret_key = fh.read().decode(
                        "utf-8"
                    )

            else:

                secret_key = os.urandom(
                    24
                ).hex()

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


    # ========================================================
    # ADMIN CONFIGURATION
    # ========================================================

    app.config["ADMIN_USERNAME"] = os.environ.get(
        "ADMIN_USERNAME",
        "admin"
    )

    app.config["ADMIN_PASSWORD"] = os.environ.get(
        "ADMIN_PASSWORD",
        "admin123"
    )


    # ========================================================
    # DATABASE CONFIGURATION
    # ========================================================

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
            + os.path.abspath(db_path).replace(
                "\\",
                "/"
            )
        )


    # Render/PostgreSQL compatibility

    if database_url.startswith("postgres://"):

        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )


    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["DEBUG"] = (
        os.environ.get(
            "FLASK_DEBUG",
            "0"
        ) == "1"
    )


    # ========================================================
    # INITIALIZE DATABASE
    # ========================================================

    db.init_app(app)


    # ========================================================
    # ACTIVE VIEWERS
    # ========================================================

    import threading

    ACTIVE_VIEWERS = {}

    ACTIVE_VIEWERS_LOCK = threading.Lock()


    # ========================================================
    # LOGIN MANAGER
    # ========================================================

    login_manager = LoginManager()

    login_manager.login_view = "auth.login"

    login_manager.init_app(app)


    from models import User


    @login_manager.user_loader
    def load_user(user_id):

        try:

            return User.query.get(
                int(user_id)
            )

        except Exception:

            return None


    # ========================================================
    # BLUEPRINTS
    # ========================================================

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


    # ========================================================
    # GLOBAL SITE STATISTICS
    # ========================================================

    @app.context_processor
    def inject_site_stats():

        from models import (
            PageView,
            Poem,
            Category,
            Favorite,
            User
        )

        # ----------------------------------------------------
        # TOTAL POEMS
        # ----------------------------------------------------

        try:

            total_poems = (
                Poem.query
                .filter_by(published=True)
                .count()
            )

        except Exception:

            total_poems = 0


        # ----------------------------------------------------
        # TOTAL CATEGORIES
        # ----------------------------------------------------

        try:

            total_categories = (
                Category.query.count()
            )

        except Exception:

            total_categories = 0


        # ----------------------------------------------------
        # TOTAL FAVORITES
        # ----------------------------------------------------

        try:

            total_favorites = (
                Favorite.query.count()
            )

        except Exception:

            total_favorites = 0


        # ----------------------------------------------------
        # REGISTERED USERS
        # ----------------------------------------------------

        try:

            registered_users = (
                User.query.count()
            )

        except Exception:

            registered_users = 0


        # ----------------------------------------------------
        # TOTAL WEBSITE VIEWS
        # ----------------------------------------------------

        try:

            total_views = (
                db.session
                .query(
                    db.func.coalesce(
                        db.func.sum(
                            PageView.count
                        ),
                        0
                    )
                )
                .scalar()
                or 0
            )

        except Exception:

            total_views = 0


        # ----------------------------------------------------
        # CURRENTLY ACTIVE VIEWERS
        # ----------------------------------------------------

        try:

            cutoff = (
                datetime.utcnow()
                - timedelta(seconds=60)
            )

            active_viewers = (
                db.session
                .query(
                    db.func.count(
                        db.distinct(
                            db.column(
                                "client_id"
                            )
                        )
                    )
                )
                .select_from(
                    db.text(
                        "active_viewer"
                    )
                )
            )

            # Safer direct query below
            from models import ActiveViewer

            active_viewers = (
                ActiveViewer.query
                .filter(
                    ActiveViewer.last_seen >= cutoff
                )
                .count()
            )

        except Exception:

            active_viewers = 0


        return {

            # Existing variable
            "poems_total_views": total_views,

            # Home statistics
            "total_views": total_views,

            "total_poems": total_poems,

            "total_categories": total_categories,

            "total_favorites": total_favorites,

            "registered_users": registered_users,

            "total_users": registered_users,

            "active_viewers": active_viewers
        }


    # ========================================================
    # DATABASE INITIALIZATION
    # ========================================================

    @app.cli.command("init-db")
    def init_db():

        """Initialize database and ensure admin exists."""

        from models import db as _db

        _db.create_all()

        try:

            from auth import get_admin_user

            get_admin_user()

        except Exception:

            pass

        print(
            "Database initialized and admin user ensured."
        )


    # ========================================================
    # CREATE ADMIN
    # ========================================================

    @app.cli.command("create-admin")

    @click.option(
        "--username",
        "-u",
        required=True,
        help="Admin username"
    )

    @click.option(
        "--password",
        "-p",
        required=True,
        help="Admin password"
    )

    def create_admin(
        username,
        password
    ):

        """Create or update an administrator."""

        from models import (
            User,
            db as _db
        )

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

            _db.session.add(user)

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


    # ========================================================
    # CREATE API TOKEN
    # ========================================================

    @app.cli.command("create-token")

    @click.option(
        "--username",
        "-u",
        required=True,
        help="Admin username"
    )

    @click.option(
        "--name",
        "-n",
        required=False,
        help="Token name"
    )

    def create_token(
        username,
        name
    ):

        """Create API token for admin."""

        from models import (
            User,
            ApiToken,
            db as _db
        )

        user = (
            User.query
            .filter(
                (User.username == username)
                |
                (User.email == username)
            )
            .first()
        )


        if not user or not user.is_admin:

            print(
                "User not found or not an admin"
            )

            return


        raw = secrets.token_urlsafe(
            32
        )

        token_hash = generate_password_hash(
            raw
        )


        token = ApiToken(
            user_id=user.id,
            name=name,
            token_hash=token_hash
        )

        _db.session.add(token)

        _db.session.commit()


        print(
            "Created token for",
            username
        )

        print(
            "Raw token (store this somewhere safe):"
        )

        print(raw)


    # ========================================================
    # BACKUP SQLITE DATABASE
    # ========================================================

    @app.cli.command("backup-db")
    def backup_db_cli():

        """Create timestamped SQLite backup."""

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


        timestamp = (
            datetime.utcnow()
            .strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )


        dst = os.path.join(
            backups_dir,
            f"ink_and_echoes-{timestamp}.db"
        )


        shutil.copy2(
            src,
            dst
        )


        print(
            "Backed up DB to",
            dst
        )


    # ========================================================
    # HOME
    # ========================================================

    @app.route("/")
    def index():

        from models import (
            Poem,
            PageView,
            Category
        )


        # ----------------------------------------------------
        # HOME PAGE VIEW
        # ----------------------------------------------------

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

            page_view = None


        # ----------------------------------------------------
        # POEMS
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RECENT POEMS
        # ----------------------------------------------------

        recent_poem_ids = set()


        for poem in poems:

            if poem.created_at:

                try:

                    age = (
                        datetime.utcnow()
                        - poem.created_at
                    )

                    if age.days <= 7:

                        recent_poem_ids.add(
                            poem.id
                        )

                except Exception:

                    pass


        # ----------------------------------------------------
        # LATEST POEM
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # FEATURED POEM
        # ----------------------------------------------------

        featured_poem = (
            Poem.query
            .filter_by(
                published=True,
                is_featured=True
            )
            .order_by(
                Poem.created_at.desc()
            )
            .first()
        )


        # If there is no featured poem,
        # use latest poem as fallback.

        if featured_poem is None:

            featured_poem = latest_poem


        # ----------------------------------------------------
        # CATEGORIES
        # ----------------------------------------------------

        try:

            categories = (
                Category.query
                .order_by(
                    Category.name.asc()
                )
                .all()
            )

        except Exception:

            categories = []


        # ----------------------------------------------------
        # RENDER HOME
        # ----------------------------------------------------

        return render_template(

            "index.html",

            poems=poems,

            recent_poem_ids=recent_poem_ids,

            latest_poem=latest_poem,

            featured_poem=featured_poem,

            has_new_poem=has_new_poem,

            categories=categories,

            total_views=(
                page_view.count
                if page_view
                else 0
            )
        )


    # ========================================================
    # POEMS LIBRARY
    # ========================================================

    @app.route("/poems")
    def poems():

        from models import (
            Poem,
            PageView,
            Category,
            Favorite
        )


        # ----------------------------------------------------
        # POEMS PAGE VIEW
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

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
            .strip()
        )


        # ----------------------------------------------------
        # BASE QUERY
        # ----------------------------------------------------

        query = (
            Poem.query
            .filter_by(
                published=True
            )
        )


        # ----------------------------------------------------
        # CATEGORY FILTER
        # ----------------------------------------------------

        if (
            category_filter
            and category_filter != "all"
        ):

            try:

                query = query.filter_by(
                    category_id=int(
                        category_filter
                    )
                )

            except ValueError:

                pass


        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        if search_query:

            search_pattern = (
                f"%{search_query}%"
            )


            query = query.filter(

                (Poem.title.ilike(
                    search_pattern
                ))

                |

                (Poem.body.ilike(
                    search_pattern
                ))

                |

                (Poem.description.ilike(
                    search_pattern
                ))

            )


        # ----------------------------------------------------
        # SORTING
        # ----------------------------------------------------

        if sort_by == "oldest":

            query = query.order_by(
                Poem.created_at.asc()
            )

        elif sort_by == "a-z":

            query = query.order_by(
                Poem.title.asc()
            )

        else:

            query = query.order_by(
                Poem.created_at.desc()
            )


        poems_list = query.all()


        # ----------------------------------------------------
        # CATEGORIES
        # ----------------------------------------------------

        categories = (
            Category.query.all()
        )


        # ----------------------------------------------------
        # USER FAVORITES
        # ----------------------------------------------------

        user_favorites = []


        if current_user.is_authenticated:

            user_favorites = [

                fav.poem_id

                for fav in (
                    Favorite.query
                    .filter_by(
                        user_id=current_user.id
                    )
                    .all()
                )

            ]


        return render_template(

            "poems.html",

            poems=poems_list,

            categories=categories,

            user_favorites=user_favorites,

            current_sort=sort_by,

            current_search=search_query,

            current_category=category_filter

        )


    # ========================================================
    # FULL POEMS
    # ========================================================

    @app.route("/poems/full")
    def poems_full():

        from models import Poem


        poems_list = (
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

            poems=poems_list,

            require_login=False,

            full_view=True

        )


    # ========================================================
    # POEM DETAIL
    # ========================================================

    @app.route(
        "/poem/<int:poem_id>"
    )
    def poem_detail(
        poem_id
    ):

        from models import (
            Poem,
            Favorite,
            History
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


        # ----------------------------------------------------
        # USER HISTORY
        # ----------------------------------------------------

        if current_user.is_authenticated:

            try:

                history = History(
                    user_id=current_user.id,
                    poem_id=poem_id
                )

                db.session.add(
                    history
                )

                db.session.commit()

            except Exception:

                db.session.rollback()


        # ----------------------------------------------------
        # FAVORITE STATUS
        # ----------------------------------------------------

        is_favorited = False


        if current_user.is_authenticated:

            favorite = (
                Favorite.query
                .filter_by(
                    user_id=current_user.id,
                    poem_id=poem_id
                )
                .first()
            )


            is_favorited = (
                favorite is not None
            )


        # ----------------------------------------------------
        # PREVIOUS / NEXT POEMS
        # ----------------------------------------------------

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


        try:

            current_index = poem_ids.index(
                poem.id
            )

        except ValueError:

            current_index = 0


        previous_poem = None

        next_poem = None


        if current_index < len(poem_ids) - 1:

            previous_poem = Poem.query.get(
                poem_ids[
                    current_index + 1
                ]
            )


        if current_index > 0:

            next_poem = Poem.query.get(
                poem_ids[
                    current_index - 1
                ]
            )


        return render_template(

            "poem_detail.html",

            poem=poem,

            is_favorited=is_favorited,

            previous_poem=previous_poem,

            next_poem=next_poem

        )


    # ========================================================
    # AI COMPANION
    # ========================================================

    @app.route("/chat")
    def chat():

        return render_template(
            "chat.html"
        )


    # ========================================================
    # API — ALL POEMS
    # ========================================================

    @app.route(
        "/api/v1/poems"
    )
    def api_poems():

        from models import (
            Poem,
            Category
        )


        poems_list = (
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


        for poem in poems_list:

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

                "id": poem.id,

                "title": poem.title,

                "body": poem.body,

                "description": poem.description,

                "category": category_name,

                "tags": poem.get_tags_list(),

                "created_at": (
                    poem.created_at.isoformat()
                    if poem.created_at
                    else None
                )

            })


        return jsonify(
            output
        )


    # ========================================================
    # API — SINGLE POEM
    # ========================================================

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

            return (
                jsonify({
                    "error": "not found"
                }),
                404
            )


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

            "id": poem.id,

            "title": poem.title,

            "body": poem.body,

            "description": poem.description,

            "category": category_name,

            "tags": poem.get_tags_list(),

            "created_at": (
                poem.created_at.isoformat()
                if poem.created_at
                else None
            )

        })


    # ========================================================
    # ADMIN API AUTHORIZATION
    # ========================================================

    def _is_admin_request():

        # ----------------------------------------------------
        # LOGGED-IN ADMIN
        # ----------------------------------------------------

        try:

            if (
                current_user.is_authenticated
                and current_user.is_admin
            ):

                return True

        except Exception:

            pass


        # ----------------------------------------------------
        # X-API-KEY
        # ----------------------------------------------------

        api_key = request.headers.get(
            "X-API-KEY"
        )


        if (
            api_key
            and api_key == app.config.get(
                "SECRET_KEY"
            )
        ):

            return True


        # ----------------------------------------------------
        # BASIC AUTH
        # ----------------------------------------------------

        authorization = request.headers.get(
            "Authorization"
        )


        if (
            authorization
            and authorization.startswith(
                "Basic "
            )
        ):

            try:

                credentials = (
                    base64.b64decode(
                        authorization.split(
                            " ",
                            1
                        )[1]
                    )
                    .decode("utf-8")
                )


                username, password = (
                    credentials.split(
                        ":",
                        1
                    )
                )


                from models import User


                user = (
                    User.query
                    .filter(
                        (User.username == username)
                        |
                        (User.email == username)
                    )
                    .first()
                )


                if (
                    user
                    and user.check_password(
                        password
                    )
                    and user.is_admin
                ):

                    return True


            except Exception:

                pass


        # ----------------------------------------------------
        # BEARER TOKEN
        # ----------------------------------------------------

        if (
            authorization
            and authorization.startswith(
                "Bearer "
            )
        ):

            try:

                token = authorization.split(
                    " ",
                    1
                )[1]


                from models import ApiToken


                for api_token in (
                    ApiToken.query.all()
                ):

                    if (
                        check_password_hash(
                            api_token.token_hash,
                            token
                        )
                        and api_token.user
                        and api_token.user.is_admin
                    ):

                        return True


            except Exception:

                pass


        return False


    # ========================================================
    # API — CREATE POEM
    # ========================================================

    @app.route(
        "/api/v1/poems",
        methods=["POST"]
    )
    def api_poems_create():

        if not _is_admin_request():

            return (
                jsonify({
                    "error": "unauthorized"
                }),
                401
            )


        if not request.is_json:

            return (
                jsonify({
                    "error": "expected JSON body"
                }),
                400
            )


        payload = (
            request.get_json()
            or {}
        )


        title = (
            payload.get("title")
            or ""
        ).strip()


        body = (
            payload.get("body")
            or ""
        ).strip()


        description = (
            payload.get("description")
            or ""
        ).strip()


        category_name = (
            payload.get("category")
            or ""
        ).strip()


        tags = (
            payload.get("tags")
            or ""
        )


        if isinstance(tags, list):

            tags = ",".join(
                str(tag).strip()
                for tag in tags
                if str(tag).strip()
            )

        else:

            tags = str(tags).strip()


        published = bool(
            payload.get(
                "published",
                True
            )
        )


        if not title or not body:

            return (
                jsonify({
                    "error":
                    "title and body required"
                }),
                400
            )


        from models import (
            Poem,
            Category,
            db as _db
        )


        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        def normalize_text(value):

            return (
                " ".join(
                    (value or "")
                    .strip()
                    .split()
                )
                .lower()
            )


        normalized_title = (
            normalize_text(title)
        )

        normalized_body = (
            normalize_text(body)
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
                == normalized_title
                and
                normalize_text(
                    poem.body
                )
                == normalized_body
            ):

                return (
                    jsonify({
                        "ok": False,
                        "error": "duplicate"
                    }),
                    409
                )


        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # CREATE POEM
        # ----------------------------------------------------

        poem = Poem(

            title=title,

            body=body,

            description=description,

            category_id=(
                category.id
                if category
                else None
            ),

            tags=tags,

            published=published

        )


        _db.session.add(
            poem
        )

        _db.session.commit()


        return jsonify({

            "ok": True,

            "id": poem.id,

            "title": poem.title

        })


    # ========================================================
    # ACTIVE VIEWER PING
    # ========================================================

    @app.route(
        "/api/v1/viewers/ping",
        methods=["POST"]
    )
    def api_viewers_ping():

        if not request.is_json:

            return (
                jsonify({
                    "error":
                    "expected JSON"
                }),
                400
            )


        payload = (
            request.get_json()
            or {}
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

            return (
                jsonify({
                    "error":
                    "client_id and page required"
                }),
                400
            )


        from models import (
            ActiveViewer,
            db as _db
        )


        now = datetime.utcnow()


        viewer = (
            ActiveViewer.query
            .filter_by(
                client_id=client_id,
                page=page
            )
            .first()
        )


        if viewer is None:

            viewer = ActiveViewer(

                client_id=client_id,

                page=page,

                last_seen=now

            )

            _db.session.add(
                viewer
            )

        else:

            viewer.last_seen = now


        _db.session.commit()


        return jsonify({
            "ok": True
        })


    # ========================================================
    # ACTIVE VIEWER COUNT
    # ========================================================

    @app.route(
        "/api/v1/viewers/<page>"
    )
    def api_viewers_count(page):

        from models import ActiveViewer


        cutoff = (
            datetime.utcnow()
            - timedelta(
                seconds=60
            )
        )


        count = (
            ActiveViewer.query
            .filter(
                ActiveViewer.page == page,
                ActiveViewer.last_seen >= cutoff
            )
            .count()
        )


        return jsonify({

            "count": count,

            "page": page

        })


    # ========================================================
    # SUGGESTIONS
    # ========================================================

    @app.route(
        "/suggestions",
        methods=["GET", "POST"]
    )
    def suggestions():

        from models import Suggestion


        if request.method == "POST":

            message = (
                request.form
                .get(
                    "message"
                )
                or ""
            ).strip()


            user_id = (
                current_user.id
                if current_user.is_authenticated
                else None
            )


            if message:

                suggestion = Suggestion(

                    user_id=user_id,

                    message=message

                )


                db.session.add(
                    suggestion
                )

                db.session.commit()


                flash(
                    "Your suggestion has been saved to the margins."
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


    # ========================================================
    # ADMIN SUGGESTIONS
    # ========================================================

    @app.route(
        "/admin/suggestions"
    )
    @login_required
    def admin_suggestions():

        from models import (
            Suggestion,
            User
        )


        if not current_user.is_admin:

            flash(
                "Admin access required."
            )

            return redirect(
                url_for("index")
            )


        suggestions = (
            Suggestion.query
            .order_by(
                Suggestion.created_at.desc()
            )
            .all()
        )


        results = []


        for suggestion in suggestions:

            user = (
                User.query.get(
                    suggestion.user_id
                )
                if suggestion.user_id
                else None
            )


            results.append({

                "suggestion": suggestion,

                "user": user

            })


        users = (
            User.query
            .order_by(
                User.created_at.desc()
            )
            .all()
        )


        return render_template(

            "admin_suggestions.html",

            suggestions=results,

            users=users

        )


    # ========================================================
    # DATABASE AUTO-CREATE + SAFE MIGRATION
    # ========================================================

    with app.app_context():

        try:

            db.create_all()

        except Exception as error:

            print(
                "Database initialization warning:",
                error
            )


        # ----------------------------------------------------
        # SAFE MIGRATION FOR EXISTING DATABASE
        # ----------------------------------------------------
        #
        # Your existing PostgreSQL database may have been
        # created before the Poem.description column existed.
        #
        # This adds the missing column without deleting poems.
        # ----------------------------------------------------

        try:

            from sqlalchemy import inspect, text


            inspector = inspect(
                db.engine
            )


            table_names = (
                inspector.get_table_names()
            )


            if "poem" in table_names:

                columns = [
                    column["name"]
                    for column in inspector.get_columns(
                        "poem"
                    )
                ]


                if "description" not in columns:

                    print(
                        "Adding missing poem.description column..."
                    )


                    with db.engine.begin() as connection:

                        connection.execute(
                            text(
                                "ALTER TABLE poem "
                                "ADD COLUMN description VARCHAR(500)"
                            )
                        )


                    print(
                        "poem.description added successfully."
                    )


        except Exception as migration_error:

            print(
                "Migration check warning:",
                migration_error
            )


    return app


# ============================================================
# CREATE APPLICATION
# ============================================================

app = create_app()


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(

        debug=(
            os.environ.get(
                "FLASK_DEBUG",
                "0"
            ) == "1"
        ),

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )

    )
