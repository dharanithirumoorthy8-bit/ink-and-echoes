import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models import db, User, Poem

app = create_app()
with app.app_context():
    print('Instance path:', app.instance_path)
    secret_file = os.path.join(app.instance_path, 'secret_key')
    print('Secret key exists:', os.path.exists(secret_file))
    db_path = os.path.join(app.instance_path, 'ink_and_echoes.db')
    print('DB file path:', db_path)
    print('DB file exists:', os.path.exists(db_path))

    # ensure tables exist
    db.create_all()

    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        print('Admin user:', admin.username, '| email:', admin.email)
    else:
        print('No admin user found')

    poems = Poem.query.order_by(Poem.created_at.asc()).all()
    print('Poem count:', len(poems))
    for p in poems:
        created = p.created_at.isoformat() if p.created_at else 'unknown'
        print(f' - id={p.id} title={p.title!r} created_at={created}')
