import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a9b3c8d1e4f7g2h6i5j8k3l2m1n9o4p'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'GradeNet'