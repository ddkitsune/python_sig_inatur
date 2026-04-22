import os
import unittest
import json
from app import create_app
from models import db, User, State, Municipality, Category, TouristProvider

class SIGINATURTestCase(unittest.TestCase):
    def setUp(self):
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing forms
        
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()
        self._seed_data()


    def _seed_data(self):
        # 1. Crear usuario administrador de prueba
        admin_user = User(name='Admin Test', email='admin@test.com', role='administrador')
        admin_user.set_password('123456')
        db.session.add(admin_user)

        # 2. Crear datos maestros básicos
        state = State(name='Estado Test')
        db.session.add(state)
        db.session.commit()

        mun = Municipality(name='Municipio Test', state_id=state.id)
        db.session.add(mun)

        cat = Category(name='Hotel Test')
        db.session.add(cat)
        db.session.commit()

        # 3. Crear proveedor turístico
        provider = TouristProvider(
            num_rtn='12345',
            rif='J-12345678-9',
            razon_social='Hotel Paraíso Test',
            direccion='Calle Falsa 123',
            telefono='0414-1234567',
            email='contacto@hotelparaiso.test',
            category_id=cat.id,
            municipality_id=mun.id,
            status='activo',
            capacity=100,
            created_by=admin_user.id
        )
        db.session.add(provider)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # --- PRUEBAS GLOBALES ---
    def test_index_redirect(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn(b'/login', response.data)

    # --- PRUEBAS DE AUTENTICACION ---
    def test_login_page(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_successful_login(self):
        response = self.login('admin@test.com', '123456')
        self.assertEqual(response.status_code, 200)

    def test_invalid_login(self):
        response = self.login('admin@test.com', 'wrongpassword')
        self.assertIn(b'incorrectos', response.data)

    # --- PRUEBAS DE ACCESO A RUTAS RESTRINGIDAS ---
    def test_dashboard_access(self):
        # Sin login redirige
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)

        # Con login entra
        self.login('admin@test.com', '123456')
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)

    def test_providers_index(self):
        self.login('admin@test.com', '123456')
        response = self.client.get('/providers')
        self.assertEqual(response.status_code, 200)

    def test_users_index(self):
        self.login('admin@test.com', '123456')
        response = self.client.get('/users')
        self.assertEqual(response.status_code, 200)

    def test_reports_index(self):
        self.login('admin@test.com', '123456')
        response = self.client.get('/reports/rtn')
        self.assertEqual(response.status_code, 200)

    def test_admin_index(self):
        self.login('admin@test.com', '123456')
        response = self.client.get('/admin/backups')
        self.assertEqual(response.status_code, 200)

    # --- PRUEBAS API DE IA ---
    def test_ia_chat_endpoint_exists(self):
        self.login('admin@test.com', '123456')
        response = self.client.post('/ia/chat', json={"message": "Hola"})
        # 200 o un error interno si falla el modelo, pero verificamos que no sea 404
        self.assertNotEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
