import random
from datetime import datetime, timedelta
from faker import Faker
from app import create_app
from models import db, TouristProvider, Category, Municipality, User

fake = Faker(['es_ES'])
app = create_app()

def seed_fake_data(count=100):
    with app.app_context():
        # Obtener IDs existentes para relaciones
        categories = Category.query.all()
        municipalities = Municipality.query.all()
        admin_user = User.query.filter_by(role='administrador').first()
        
        if not categories or not municipalities or not admin_user:
            print("Error: Asegúrate de haber corrido seed.py primero para tener categorías, municipios y usuarios.")
            return

        print(f"Generando {count} prestadores de prueba...")
        
        status_options = ['activo', 'inactivo', 'vencido', 'suspendido']
        
        for i in range(count):
            # RTN aleatorio: Numero de 5-7 digitos
            rtn = str(random.randint(10000, 999999))
            # RIF aleatorio: J-12345678-9
            rif = f"J-{random.randint(10000000, 99999999)}-{random.randint(0, 9)}"
            
            # Evitar duplicados simples en este loop
            if TouristProvider.query.filter_by(num_rtn=rtn).first() or \
               TouristProvider.query.filter_by(rif=rif).first():
                continue

            # Fecha aleatoria (entre hace 1 año y dentro de 2 años)
            days_offset = random.randint(-365, 730)
            valid_until = (datetime.now() + timedelta(days=days_offset)).date()
            
            # Estatus coherente con la fecha
            status = random.choice(status_options)
            if valid_until < datetime.now().date() and status == 'activo':
                status = 'vencido'

            provider = TouristProvider(
                num_rtn=rtn,
                rif=rif,
                razon_social=fake.company(),
                direccion=fake.address(),
                telefono=fake.phone_number(),
                email=fake.company_email(),
                category_id=random.choice(categories).id,
                municipality_id=random.choice(municipalities).id,
                status=status,
                valid_until=valid_until,
                capacity=random.randint(5, 500),
                created_by=admin_user.id
            )
            db.session.add(provider)
            
            if (i + 1) % 20 == 0:
                db.session.commit()
                print(f"  {i + 1} registros creados...")

        db.session.commit()
        print("¡Proceso de generación masiva completado con éxito!")

if __name__ == '__main__':
    seed_fake_data(100)
