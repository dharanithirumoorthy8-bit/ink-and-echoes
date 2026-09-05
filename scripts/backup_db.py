import os
import sys
import shutil
import datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

app = create_app()

if __name__ == '__main__':
    src = os.path.join(app.instance_path, 'ink_and_echoes.db')
    if not os.path.exists(src):
        print('No DB file at', src)
        sys.exit(1)
    backups_dir = os.path.join(app.instance_path, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    dst = os.path.join(backups_dir, f'ink_and_echoes-{ts}.db')
    shutil.copy2(src, dst)
    print('Backed up DB to', dst)
