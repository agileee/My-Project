from flask import Flask
from flask_mysqldb import MySQL
import hashlib

mysql = MySQL()  # Initialize MySQL

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'

    # MySQL Configuration
    app.config["MYSQL_HOST"] = "localhost"
    app.config["MYSQL_USER"] = "your_user"
    app.config["MYSQL_PASSWORD"] = "your_password"
    app.config["MYSQL_DB"] = "finance"

    mysql.init_app(app)  # Initialize MySQL with the app

    from .routes import main  # Import routes (Blueprint)
    app.register_blueprint(main)

    return app
