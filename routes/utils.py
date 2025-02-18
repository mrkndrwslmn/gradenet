import mysql.connector  
from flask import current_app  

def get_db_connection():
    """Connects to the database and returns a connection object."""
    try:
        # Access configuration values using current_app.config
        conn = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")  # Log this!
        return None  # Or raise the exception after logging if you prefer to crash the app