from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import TouristProvider, Category, State, Municipality, db
from datetime import datetime

providers_bp = Blueprint('providers', __name__)

@providers_bp.route('/providers')
@login_required
def index():
    query = TouristProvider.query

    # Filtro de búsqueda de texto (RTN, RIF, razón social)
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (TouristProvider.num_rtn.ilike(f'%{search}%')) |
            (TouristProvider.razon_social.ilike(f'%{search}%')) |
            (TouristProvider.rif.ilike(f'%{search}%'))
        )

    # Filtro por categoría
    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter(TouristProvider.category_id == category_id)

    # Filtro por estado (a través del municipio)
    state_id = request.args.get('state_id', type=int)
    if state_id:
        muni_ids = [m.id for m in Municipality.query.filter_by(state_id=state_id).all()]
        query = query.filter(TouristProvider.municipality_id.in_(muni_ids))

    # Filtro por estatus
    status_filter = request.args.get('status', '').strip()
    if status_filter in ('activo', 'vencido', 'tramite'):
        query = query.filter(TouristProvider.status == status_filter)

    # Filtro por rango de fecha de vencimiento
    valid_from = request.args.get('valid_from', '').strip()
    valid_to = request.args.get('valid_to', '').strip()
    if valid_from:
        try:
            valid_from_dt = datetime.strptime(valid_from, '%Y-%m-%d').date()
            query = query.filter(TouristProvider.valid_until >= valid_from_dt)
        except ValueError:
            pass
    if valid_to:
        try:
            valid_to_dt = datetime.strptime(valid_to, '%Y-%m-%d').date()
            query = query.filter(TouristProvider.valid_until <= valid_to_dt)
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(TouristProvider.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    categories = Category.query.order_by(Category.name).all()
    states = State.query.order_by(State.name).all()
    return render_template(
        'providers/index.html',
        providers=pagination.items,
        pagination=pagination,
        categories=categories,
        states=states,
        filters={
            'search': search,
            'category_id': category_id,
            'state_id': state_id,
            'status': status_filter,
            'valid_from': valid_from,
            'valid_to': valid_to,
        }
    )

@providers_bp.route('/providers/export/csv')
@login_required
def export_csv():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    providers = TouristProvider.query.all()
    data = []
    for p in providers:
        data.append({
            'RTN': p.num_rtn,
            'RIF': p.rif,
            'Razón Social': p.razon_social,
            'Categoría': p.category.name,
            'Estado': p.municipality.state.name,
            'Municipio': p.municipality.name,
            'Estatus': p.status,
            'Vence': p.valid_until.strftime('%d/%m/%Y') if p.valid_until else ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'reporte_rtn_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    )

@providers_bp.route('/providers/create', methods=['GET', 'POST'])
@login_required
def create():
    categories = Category.query.all()
    states = State.query.all()
    if request.method == 'POST':
        num_rtn = request.form['num_rtn'].strip()
        rif = request.form['rif'].strip()

        # Validar unicidad
        if TouristProvider.query.filter_by(num_rtn=num_rtn).first():
            flash(f'El RTN "{num_rtn}" ya está registrado.', 'error')
            return render_template('providers/create.html', categories=categories, states=states)
        if TouristProvider.query.filter_by(rif=rif).first():
            flash(f'El RIF "{rif}" ya está registrado.', 'error')
            return render_template('providers/create.html', categories=categories, states=states)

        try:
            new_provider = TouristProvider(
                num_rtn=num_rtn,
                rif=rif,
                razon_social=request.form['razon_social'],
                direccion=request.form['direccion'],
                telefono=request.form['telefono'],
                email=request.form['email'],
                category_id=request.form['category_id'],
                municipality_id=request.form['municipality_id'],
                status=request.form['status'],
                valid_until=datetime.strptime(request.form['valid_until'], '%Y-%m-%d').date() if request.form.get('valid_until') else None,
                capacity=int(request.form.get('capacity', 0)),
                created_by=current_user.id
            )
            db.session.add(new_provider)
            db.session.commit()
            flash('Prestador registrado exitosamente.', 'success')
            return redirect(url_for('providers.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar prestador: {str(e)}', 'error')

    return render_template('providers/create.html', categories=categories, states=states)

@providers_bp.route('/providers/<int:id>/show')
@login_required
def show(id):
    provider = TouristProvider.query.get_or_404(id)
    return render_template('providers/show.html', provider=provider)

@providers_bp.route('/providers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    provider = TouristProvider.query.get_or_404(id)
    categories = Category.query.all()
    states = State.query.all()
    if request.method == 'POST':
        num_rtn = request.form['num_rtn'].strip()
        rif = request.form['rif'].strip()

        # Validar unicidad excluyendo el propio registro
        dup_rtn = TouristProvider.query.filter(
            TouristProvider.num_rtn == num_rtn,
            TouristProvider.id != id
        ).first()
        if dup_rtn:
            flash(f'El RTN "{num_rtn}" ya está en uso por otro prestador.', 'error')
            return render_template('providers/edit.html', provider=provider, categories=categories, states=states)

        dup_rif = TouristProvider.query.filter(
            TouristProvider.rif == rif,
            TouristProvider.id != id
        ).first()
        if dup_rif:
            flash(f'El RIF "{rif}" ya está en uso por otro prestador.', 'error')
            return render_template('providers/edit.html', provider=provider, categories=categories, states=states)

        try:
            provider.num_rtn = num_rtn
            provider.rif = rif
            provider.razon_social = request.form['razon_social']
            provider.direccion = request.form['direccion']
            provider.telefono = request.form['telefono']
            provider.email = request.form['email']
            provider.category_id = request.form['category_id']
            provider.municipality_id = request.form['municipality_id']
            provider.status = request.form['status']
            provider.valid_until = datetime.strptime(request.form['valid_until'], '%Y-%m-%d').date() if request.form.get('valid_until') else None
            provider.capacity = int(request.form.get('capacity', 0))
            provider.updated_by = current_user.id

            db.session.commit()
            flash('Prestador actualizado exitosamente.', 'success')
            return redirect(url_for('providers.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar prestador: {str(e)}', 'error')

    return render_template('providers/edit.html', provider=provider, categories=categories, states=states)

@providers_bp.route('/providers/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    provider = TouristProvider.query.get_or_404(id)
    try:
        db.session.delete(provider)
        db.session.commit()
        flash('Prestador eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar prestador: {str(e)}', 'error')
    return redirect(url_for('providers.index'))
