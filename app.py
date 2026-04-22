import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from models import db, User
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-sig-inatur')
    
    # Asegurar que la base de datos se busque siempre en la carpeta 'instance'
    db_path = os.path.join(app.instance_path, 'sig_inatur.db')
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f"sqlite:///{db_path}")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate = Migrate(app, db)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debe iniciar sesión para acceder a esta página.'
    login_manager.login_message_category = 'error'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Blueprints ────────────────────────────────────────────────
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.providers import providers_bp
    from blueprints.users import users_bp
    from blueprints.reports import reports_bp
    from blueprints.admin import admin_bp
    from blueprints.ia import ia_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(providers_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ia_bp)

    @app.route('/')
    def index_redirect():
        return redirect(url_for('dashboard.index'))

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
