import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models import db, User, Poem, ActiveViewer

app = create_app()
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        print('Admin:', admin.username, admin.email)
    else:
        print('No admin user')

    poems = Poem.query.order_by(Poem.id.asc()).all()
    print('\nPoems count:', len(poems))
    for p in poems:
        print(f' - id={p.id} title="{p.title}" created_at={p.created_at}')

    avs = ActiveViewer.query.order_by(ActiveViewer.last_seen.desc()).all()
    print('\nActive viewers count (saved):', len(avs))
    for a in avs[:50]:
        print(f' - client_id={a.client_id} page={a.page} last_seen={a.last_seen}')

    print('\nDB file:', os.path.join(app.instance_path, 'ink_and_echoes.db'))
