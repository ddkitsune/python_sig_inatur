from flask import Flask
from models import db, User, Category, State, Municipality, TouristProvider
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///sig_inatur.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def seed():
    with app.app_context():
        print("Limpiando base de datos...")
        db.drop_all()
        db.create_all()

        print("Creando usuarios iniciales...")
        admin = User(name='Deivy (Administrador)', email='admin@inatur.gob.ve', role='administrador')
        admin.set_password('admin123')
        db.session.add(admin)

        gerente = User(name='Gerente Sigma', email='gerente@inatur.gob.ve', role='gerente')
        gerente.set_password('gerente123')
        db.session.add(gerente)

        tecnico = User(name='Técnico Sigma', email='tecnico@inatur.gob.ve', role='tecnico')
        tecnico.set_password('tecnico123')
        db.session.add(tecnico)

        print("Cargando categorías...")
        cat_aloj = Category(name='Alojamiento')
        cat_alim = Category(name='Alimentos y Bebidas')
        cat_agencia = Category(name='Agencias de Viajes')
        cat_recre = Category(name='Recreación')
        cat_transp = Category(name='Transporte Turístico')
        db.session.add_all([cat_aloj, cat_alim, cat_agencia, cat_recre, cat_transp])
        db.session.flush()

        print("Cargando división territorial...")
        st_merida = State(name='Mérida')
        st_nueva_esp = State(name='Nueva Esparta')
        st_falcon = State(name='Falcón')
        db.session.add_all([st_merida, st_nueva_esp, st_falcon])
        db.session.flush()

        m_libertador = Municipality(name='Libertador', state_id=st_merida.id)
        m_marino = Municipality(name='Mariño', state_id=st_nueva_esp.id)
        m_silva = Municipality(name='Silva', state_id=st_falcon.id)
        db.session.add_all([m_libertador, m_marino, m_silva])
        db.session.flush()

        print("Creando prestadores demostrativos fijos...")
        demo_providers = [
            TouristProvider(num_rtn="12345", rif="J-30123456-1", razon_social="Hotel Gran Sol de Mérida", direccion="Av. Las Américas, Mérida", telefono="0274-2661122", email="contacto@gransolmerida.com", category_id=cat_aloj.id, municipality_id=m_libertador.id, status='activo', valid_until=date(2027, 12, 31), capacity=120, created_by=admin.id),
            TouristProvider(num_rtn="54321", rif="J-40555666-0", razon_social="Restaurante La Perla del Caribe", direccion="Playa El Agua, Margarita", telefono="0295-2634455", email="ventas@laperlamargarita.com", category_id=cat_alim.id, municipality_id=m_marino.id, status='vencido', valid_until=date(2025, 3, 15), capacity=60, created_by=admin.id),
            TouristProvider(num_rtn="98765", rif="J-50999888-2", razon_social="Posada Morrocoy Blue", direccion="Tucacas, Sector Punta Brava", telefono="0259-8123344", email="reservas@morrocoyblue.ve", category_id=cat_aloj.id, municipality_id=m_silva.id, status='tramite', valid_until=date(2026, 6, 20), capacity=45, created_by=admin.id)
        ]
        db.session.add_all(demo_providers)
        db.session.commit()
        print("Base de datos poblada con éxito.")

if __name__ == '__main__':
    seed()
