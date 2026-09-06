import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_login import login_user, logout_user, login_required, current_user

from models import User, db

auth_bp = Blueprint('auth', __name__)


def get_admin_credentials():
    admin_username = (os.environ.get('ADMIN_USERNAME') or 'admin').strip() or 'admin'
    admin_password = os.environ.get('ADMIN_PASSWORD') or 'admin123'
    return admin_username, admin_password


def get_admin_user():
    admin_username, admin_password = get_admin_credentials()

    user = User.query.filter_by(username=admin_username).first()
    if user is None:
        user = User(
            username=admin_username,
            email=f'{admin_username}@admin.local',
            dob=None,
            is_admin=True,
        )
        user.set_password(admin_password)
        db.session.add(user)
        db.session.commit()
        return user

    user.is_admin = True
    user.set_password(admin_password)
    db.session.commit()
    return user


def parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        flash('You are already logged in.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        dob = parse_date(request.form.get('dob') or '')

        admin_username, _ = get_admin_credentials()
        admin_email = f'{admin_username}@admin.local'
        if not username or not email or not password or dob is None:
            flash('Please complete every field with a valid date of birth.')
            return redirect(url_for('auth.signup'))
        if username.lower() == admin_username.lower() or email == admin_email.lower():
            flash('That username is reserved for the administrator.')
            return redirect(url_for('auth.signup'))
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('That username or email is already registered. Please log in.')
            return redirect(url_for('auth.login'))

        user = User(username=username, email=email, dob=dob, is_admin=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created. You can now log in anytime.')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        admin_username, admin_password = get_admin_credentials()
        if username == admin_username and password == admin_password:
            login_user(get_admin_user())
            flash('Logged in as administrator.')
            return redirect(url_for('admin.admin_index'))

        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in.')
            return redirect(url_for('index'))
        flash('Invalid credentials.')
        return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('index'))
