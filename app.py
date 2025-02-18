from flask import Flask, redirect, url_for
from config import Config
import mysql.connector
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "YOUR_SECRET_KEY"

csrf = CSRFProtect(app)

def get_db_connection():
    """Connects to the database and returns a connection object."""
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")  # Log this!
        return None  # Or raise the exception after logging if you prefer to crash the app

# Add min function to Jinja2 environment
app.jinja_env.globals.update(min=min)

# Import routes after initializing app and defining get_db_connection
from routes import dean_routes, faculty_routes, student_routes, subject_routes
from routes.auth_routes import bp, login_manager

login_manager.init_app(app)
app.register_blueprint(bp, url_prefix='/auth')

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

def register_blueprints(app):
    app.register_blueprint(dean_routes.bp)
    app.register_blueprint(faculty_routes.bp)
    app.register_blueprint(student_routes.bp)
    app.register_blueprint(subject_routes.bp)

if __name__ == '__main__':
    register_blueprints(app)
    app.run(debug=True)