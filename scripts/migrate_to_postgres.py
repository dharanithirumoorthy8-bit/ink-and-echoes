"""
Migrate data from the current app SQLite DB to a Postgres database.
Usage:
  export DATABASE_URL=postgresql://user:pass@host:port/dbname
  python scripts/migrate_to_postgres.py

The script will create tables in the target Postgres DB and copy rows from the SQLite DB.
"""
import os
import sys
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models import db, User, Category, Poem, ApiToken, ActiveViewer, Suggestion, Favorite, PageView, History
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def main():
    target = os.environ.get('DATABASE_URL')
    if not target:
        if len(sys.argv) > 1:
            target = sys.argv[1]
        else:
            print('Provide target DATABASE_URL via env or first arg')
            sys.exit(1)

    print('Target:', target)
    app = create_app()
    # source session
    with app.app_context():
        SourceSession = db.session.__class__
        source_session = db.session

        # create target engine and session
        target_engine = create_engine(target)
        TargetSession = sessionmaker(bind=target_engine)
        target_sess = TargetSession()

        # create tables on target
        print('Creating tables on target...')
        db.metadata.create_all(bind=target_engine)

        # copy users
        print('Copying users...')
        for u in source_session.query(User).all():
            nu = User(id=u.id, username=u.username, email=u.email, password_hash=u.password_hash, dob=u.dob, is_admin=u.is_admin, created_at=u.created_at)
            target_sess.merge(nu)
        target_sess.commit()

        # categories
        print('Copying categories...')
        for c in source_session.query(Category).all():
            nc = Category(id=c.id, name=c.name)
            target_sess.merge(nc)
        target_sess.commit()

        # poems
        print('Copying poems...')
        for p in source_session.query(Poem).all():
            np = Poem(id=p.id, title=p.title, body=p.body, published=p.published, category_id=p.category_id, created_at=p.created_at)
            target_sess.merge(np)
        target_sess.commit()

        # suggestions
        print('Copying suggestions...')
        for s in source_session.query(Suggestion).all():
            ns = Suggestion(id=s.id, user_id=s.user_id, message=s.message, created_at=s.created_at)
            target_sess.merge(ns)
        target_sess.commit()

        # pageviews
        print('Copying page views...')
        for pv in source_session.query(PageView).all():
            npv = PageView(id=pv.id, page=pv.page, count=pv.count, updated_at=pv.updated_at)
            target_sess.merge(npv)
        target_sess.commit()

        # favorites
        print('Copying favorites...')
        for f in source_session.query(Favorite).all():
            nf = Favorite(id=f.id, user_id=f.user_id, poem_id=f.poem_id)
            target_sess.merge(nf)
        target_sess.commit()

        # history
        print('Copying history...')
        for h in source_session.query(History).all():
            nh = History(id=h.id, user_id=h.user_id, poem_id=h.poem_id, viewed_at=h.viewed_at)
            target_sess.merge(nh)
        target_sess.commit()

        # api tokens
        print('Copying api tokens...')
        for t in source_session.query(ApiToken).all():
            nt = ApiToken(id=t.id, user_id=t.user_id, name=t.name, token_hash=t.token_hash, created_at=t.created_at)
            target_sess.merge(nt)
        target_sess.commit()

        # active viewers
        print('Copying active viewers...')
        for v in source_session.query(ActiveViewer).all():
            nv = ActiveViewer(id=v.id, client_id=v.client_id, page=v.page, last_seen=v.last_seen)
            target_sess.merge(nv)
        target_sess.commit()

        print('Migration complete.')


if __name__ == '__main__':
    main()
