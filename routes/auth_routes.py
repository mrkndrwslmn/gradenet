from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from forms import LoginForm
from app import get_db_connection #No `.` from routes.auth_routes import get_db_connection - depending where you put this function
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

bp = Blueprint('auth', __name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Specify the login route

@login_manager.user_loader
def load_user(user_id):
    """Loads a user from the database given a user ID."""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()

        if user_data:
            user_data.pop('password', None)  # Remove unexpected field
            allowed_keys = {
                "user_id", "first_name", "middle_name", "last_name", "username", "email", "phone",
                "role", "date_of_birth", "gender", "is_active", "student_number", "section", "year_level", "semester", "created_at"
            }
            filtered_data = {k: v for k, v in user_data.items() if k in allowed_keys}
            if "is_active" not in filtered_data:
                filtered_data["is_active"] = 1
            user = User(**filtered_data)
            return user
        else:
            return None
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


class User(UserMixin):  # Extend UserMixin
    def __init__(self, user_id, first_name, middle_name, last_name, username, email, phone, role, date_of_birth, gender, is_active=1, created_at=None):
        self.id = user_id  # flask_login requirement
        self.user_id = user_id
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.username = username  # new attribute
        self.email = email
        self.phone = phone
        self.role = role
        self.date_of_birth = date_of_birth
        self._is_active = is_active  # store passed is_active in a private attribute
        self.gender = gender
        self.created_at = created_at

    @property
    def is_active(self):
        # Return True if _is_active is truthy (1), else False
        return bool(self._is_active)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email='{self.email}')>"

@bp.route('/login', methods=['GET', 'POST'])
def login():
    print("Login route triggered. Method:", request.method)
    form = LoginForm()
    if form.validate_on_submit():
        print("Form validated. Checking database for user...")
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('index.html', form=form)

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s", (form.username.data,))
            user_data = cursor.fetchone()

            print("User data:", user_data)
            form.password.data = form.password.data.strip()
            print("Form password:", form.password.data)
            if user_data and user_data.get('password') and check_password_hash(user_data['password'], form.password.data):
                user_data.pop('password', None)  # Remove unexpected parameter
                user = User(**user_data) 
                login_user(user)  

                if user.role in ('Dean', 'Secretary'):
                    return redirect(url_for('dean.dashboard'))
                elif user.role == 'Faculty':
                    return redirect(url_for('faculty.dashboard'))
                elif user.role == 'Student':
                    return redirect(url_for('student.dashboard'))
                else:
                    flash('Invalid role.', 'error')
                    return render_template('index.html', form=form)
            else:
                flash('Invalid username or password', 'error')
                return render_template('index.html', form=form)

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash(f"Database error: {err}", "error")
            return render_template('index.html', form=form)
        finally:
            cursor.close()
            conn.close()
    else:
        if request.method == 'POST':
            flash("Form data missing or invalid", "error")
            print("Form errors:", form.errors)

        return render_template('index.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
