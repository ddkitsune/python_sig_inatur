import os
import subprocess
import glob
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')


def admin_required(f):
    """Decorador que restringe el acceso solo a administradores."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'administrador':
            flash('Acceso denegado. Se requiere rol de Administrador.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _list_backups():
    _ensure_backup_dir()
    files = []
    for path in glob.glob(os.path.join(BACKUP_DIR, '*.sql')):
        stat = os.stat(path)
        files.append({
            'name': os.path.basename(path),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'modified_dt': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
        })
    files.sort(key=lambda x: x['modified'], reverse=True)
    return files


def _get_db_config():
    """Extrae la configuración de BD desde la URI de SQLAlchemy."""
    from flask import current_app
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    # Soportar formato: postgresql://user:pass@host:port/dbname
    if not uri.startswith('postgresql://') and not uri.startswith('postgres://'):
        return None  # Solo soportamos PostgreSQL para respaldos
    try:
        # Extraer componentes de la URI
        rest = uri.split('://', 1)[1]
        userpass, hostrest = rest.split('@', 1)
        user, password = (userpass.split(':', 1) + [''])[:2]
        hostport, dbname = hostrest.split('/', 1)
        if ':' in hostport:
            host, port = hostport.split(':', 1)
        else:
            host, port = hostport, '5432'
        return {'user': user, 'password': password, 'host': host, 'port': port, 'dbname': dbname}
    except Exception:
        return None


# ─── Rutas ────────────────────────────────────────────────────────────────────

@admin_bp.route('/backups')
@login_required
@admin_required
def backups_index():
    files = _list_backups()
    return render_template('admin/backups.html', files=files)


@admin_bp.route('/backups/create', methods=['POST'])
@login_required
@admin_required
def backups_create():
    _ensure_backup_dir()
    cfg = _get_db_config()

    if cfg is None:
        # SQLite: simplemente copiamos el archivo .db
        from flask import current_app
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri.startswith('sqlite:///'):
            db_path = uri.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
            if os.path.isfile(db_path):
                import shutil
                ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                dest = os.path.join(BACKUP_DIR, f'backup_{ts}.sql')
                # Para SQLite "exportamos" como copia con extensión .sql para consistencia
                shutil.copy2(db_path, dest)
                flash(f'Respaldo SQLite creado: backup_{ts}.sql', 'success')
            else:
                flash('No se encontró el archivo de base de datos SQLite.', 'error')
        else:
            flash('Tipo de base de datos no soportado para respaldos automáticos.', 'error')
    else:
        # PostgreSQL: usamos pg_dump
        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        filename = f'backup_{ts}.sql'
        dest = os.path.join(BACKUP_DIR, filename)
        env = os.environ.copy()
        if cfg['password']:
            env['PGPASSWORD'] = cfg['password']
        cmd = [
            'pg_dump',
            '-h', cfg['host'],
            '-p', cfg['port'],
            '-U', cfg['user'],
            '-d', cfg['dbname'],
            '-f', dest,
            '--no-password',
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
            if result.returncode == 0:
                flash(f'Respaldo PostgreSQL creado correctamente: {filename}', 'success')
            else:
                flash(f'Error al ejecutar pg_dump: {result.stderr}', 'error')
        except FileNotFoundError:
            flash('Error: No se encontró el ejecutable "pg_dump". Asegúrese de tener PostgreSQL instalado en el PATH.', 'error')
        except subprocess.TimeoutExpired:
            flash('El proceso de respaldo tardó demasiado y fue cancelado.', 'error')

    return redirect(url_for('admin.backups_index'))


@admin_bp.route('/backups/<filename>/download')
@login_required
@admin_required
def backups_download(filename):
    _ensure_backup_dir()
    safe_name = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(path) or not safe_name.endswith('.sql'):
        flash('Archivo de respaldo no encontrado.', 'error')
        return redirect(url_for('admin.backups_index'))
    return send_file(path, as_attachment=True, download_name=safe_name)


@admin_bp.route('/backups/<filename>/delete', methods=['POST'])
@login_required
@admin_required
def backups_delete(filename):
    _ensure_backup_dir()
    safe_name = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe_name)
    if os.path.isfile(path) and safe_name.endswith('.sql'):
        os.remove(path)
        flash(f'Respaldo "{safe_name}" eliminado correctamente.', 'success')
    else:
        flash('Archivo de respaldo no encontrado.', 'error')
    return redirect(url_for('admin.backups_index'))


@admin_bp.route('/backups/<filename>/restore', methods=['POST'])
@login_required
@admin_required
def backups_restore(filename):
    confirmation = request.form.get('confirm', '')
    if confirmation != 'SI':
        flash('Debe confirmar la restauración escribiendo "SI".', 'error')
        return redirect(url_for('admin.backups_index'))

    _ensure_backup_dir()
    safe_name = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.isfile(path) or not safe_name.endswith('.sql'):
        flash('Archivo de respaldo no encontrado.', 'error')
        return redirect(url_for('admin.backups_index'))

    cfg = _get_db_config()
    if cfg is None:
        flash('La restauración automática solo está soportada para bases de datos PostgreSQL.', 'error')
        return redirect(url_for('admin.backups_index'))

    env = os.environ.copy()
    if cfg['password']:
        env['PGPASSWORD'] = cfg['password']

    cmd = [
        'psql',
        '-h', cfg['host'],
        '-p', cfg['port'],
        '-U', cfg['user'],
        '-d', cfg['dbname'],
        '-f', path,
        '--no-password',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
        if result.returncode == 0:
            flash(f'Base de datos restaurada correctamente desde "{safe_name}". Reinicie sesión si los datos no se reflejan inmediatamente.', 'success')
        else:
            flash(f'Error al restaurar: {result.stderr[:500]}', 'error')
    except FileNotFoundError:
        flash('Error: No se encontró el ejecutable "psql". Asegúrese de tener PostgreSQL instalado en el PATH.', 'error')
    except subprocess.TimeoutExpired:
        flash('El proceso de restauración tardó demasiado y fue cancelado.', 'error')

    return redirect(url_for('admin.backups_index'))
