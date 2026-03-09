from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User, db
from functools import wraps

users_bp = Blueprint('users', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'administrador':
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@users_bp.route('/users')
@login_required
@admin_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    query = User.query
    if search:
        query = query.filter(
            User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%')
        )
    pagination = query.order_by(User.name).paginate(page=page, per_page=15, error_out=False)
    return render_template('users/index.html', users=pagination.items, pagination=pagination, search=search)

@users_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            password_confirm = request.form.get('password_confirm', '')
            role = request.form['role']

            if password != password_confirm:
                flash('Las contraseñas no coinciden.', 'error')
                return render_template('users/create.html')

            if User.query.filter_by(email=email).first():
                flash('El correo ya está registrado.', 'error')
                return render_template('users/create.html')

            new_user = User(name=name, email=email, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear usuario: {str(e)}', 'error')

    return render_template('users/create.html')

@users_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        try:
            user.name = request.form['name']
            new_email = request.form['email']
            role = request.form['role']
            password = request.form.get('password', '').strip()
            password_confirm = request.form.get('password_confirm', '').strip()

            # Validar email único (ignorando el propio)
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != id:
                flash('Ese correo ya está en uso por otro usuario.', 'error')
                return render_template('users/edit.html', user=user)

            # Validar contraseña si se provee
            if password:
                if password != password_confirm:
                    flash('Las contraseñas no coinciden.', 'error')
                    return render_template('users/edit.html', user=user)
                user.set_password(password)

            user.email = new_email
            user.role = role
            db.session.commit()
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar usuario: {str(e)}', 'error')

    return render_template('users/edit.html', user=user)

@users_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    if id == current_user.id:
        flash('No puedes eliminarte a ti mismo.', 'error')
        return redirect(url_for('users.index'))
        
    user = User.query.get_or_404(id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash('Usuario eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar usuario: {str(e)}', 'error')
    return redirect(url_for('users.index'))
