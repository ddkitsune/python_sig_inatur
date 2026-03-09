from app import create_app
from models import db, User, Category, State, Municipality
from werkzeug.security import generate_password_hash

app = create_app()

def seed():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Users
        admin = User(name='Deivy (Administrador)', email='admin@inatur.gob.ve', role='administrador')
        admin.set_password('admin123')
        db.session.add(admin)

        gerente = User(name='Gerente Sigma', email='gerente@inatur.gob.ve', role='gerente')
        gerente.set_password('gerente123')
        db.session.add(gerente)

        tecnico = User(name='Técnico Sigma', email='tecnico@inatur.gob.ve', role='tecnico')
        tecnico.set_password('tecnico123')
        db.session.add(tecnico)

        # Categories
        categories = [
            'Alimentos y Bebidas',
            'Alojamiento',
            'Agencias de Viajes',
            'Recreación',
            'Transporte Turístico',
            'Guías de Turismo'
        ]
        for cat_name in categories:
            db.session.add(Category(name=cat_name))

        # States and Municipalities
        locations = {
            'Distrito Capital': ['Libertador'],
            'Mérida': ['Libertador', 'Alberto Adriani', 'Campo Elías'],
            'Nueva Esparta': ['Mariño', 'Maneiro', 'Antolín del Campo'],
            'Falcón': ['Miranda', 'Carirubana', 'Silva'],
            'Aragua': ['Girardot', 'Santiago Mariño', 'Tovar']
        }

        for state_name, municipalities in locations.items():
            state = State(name=state_name)
            db.session.add(state)
            db.session.flush() # To get the state ID
            for mun_name in municipalities:
                db.session.add(Municipality(name=mun_name, state_id=state.id))

        db.session.commit()
        print("Base de datos poblada con éxito.")

if __name__ == '__main__':
    seed()
