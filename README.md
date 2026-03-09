# SIG-INATUR (Versión Python/Flask)

Este es una recreación del Sistema de Gestión de Información de INATUR, originalmente desarrollado en Laravel, ahora implementado utilizando Python y Flask.

## Requisitos

- Python 3.8+
- Bibliotecas listadas en `requirements.txt`

## Instalación

1. Crear un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Inicializar y poblar la base de datos:
   ```bash
   python seed.py
   ```

## Ejecución

Para iniciar el servidor de desarrollo:
```bash
python app.py
```
El sistema estará disponible en `http://127.0.0.1:5000`.

## Credenciales de Acceso (Semilla)

- **Administrador:** admin@inatur.gob.ve / admin123
- **Gerente:** gerente@inatur.gob.ve / gerente123
- **Técnico:** tecnico@inatur.gob.ve / tecnico123

## Tecnologías Utilizadas

- **Backend:** Flask
- **ORM:** SQLAlchemy
- **Autenticación:** Flask-Login
- **Frontend:** Jinja2 (Templates), Vanilla CSS, FontAwesome, Chart.js
- **Base de Datos:** SQLite (Configurable a PostgreSQL/MySQL)
