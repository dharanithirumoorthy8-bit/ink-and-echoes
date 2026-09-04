from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_login import login_user, logout_user, login_required

from models import User, db

auth_bp = Blueprint('auth', __name__)


def parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        dob_s = request.form.get('dob')
        dob = parse_date(dob_s)

        if not (username and email and password and dob):
            flash('Please fill all fields (use YYYY-MM-DD for DOB).')
            return redirect(url_for('auth.signup'))

        # age verification
        from datetime import date
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            flash('You must be 18+ to register.')
            return redirect(url_for('auth.signup'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('User with that username or email already exists.')
            return redirect(url_for('auth.signup'))

        user = User(username=username, email=email, dob=dob)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome — account created.')
        return redirect(url_for('index'))

    return render_template('signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
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
