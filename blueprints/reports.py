from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from models import TouristProvider, Category, State
from io import BytesIO
from datetime import datetime
from functools import wraps
from flask import redirect, url_for, flash

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def gerente_or_admin_required(f):
    """Solo administrador o gerente pueden acceder a reportes PDF."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('administrador', 'gerente'):
            flash('Acceso denegado. Solo Administradores y Gerentes pueden descargar reportes.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


def _build_rtn_pdf(providers, categoria=None, estado=None):
    """Genera el PDF del reporte RTN usando fpdf2."""
    from fpdf import FPDF

    class RTNReport(FPDF):
        def header(self):
            # Logo / Encabezado institucional
            self.set_fill_color(0, 51, 102)  # --primary: #003366
            self.rect(0, 0, 210, 30, 'F')

            self.set_text_color(255, 255, 255)
            self.set_font('Helvetica', 'B', 14)
            self.set_xy(10, 8)
            self.cell(0, 7, 'INSTITUTO NACIONAL DE TURISMO (INATUR)', ln=True)

            self.set_font('Helvetica', '', 10)
            self.set_x(10)
            self.cell(0, 5, 'Sistema de Informacion Gerencial - Reporte de Prestadores Turisticos (RTN)', ln=True)

            self.set_text_color(0, 0, 0)
            self.ln(8)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Generado por SIG-INATUR el {datetime.now().strftime("%d/%m/%Y %H:%M")}  |  Pag. {self.page_no()}', 0, 0, 'C')

    pdf = RTNReport(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    # --- Subtítulo / Filtros aplicados ---
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, 'Listado General de Prestadores de Servicio Turistico', ln=True)

    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(100, 100, 100)
    filtros = []
    if categoria:
        filtros.append(f'Categoria: {categoria}')
    if estado:
        filtros.append(f'Estado: {estado}')
    filtros_str = '  |  '.join(filtros) if filtros else 'Todos los registros'
    pdf.cell(0, 5, f'Filtros aplicados: {filtros_str}', ln=True)
    pdf.cell(0, 5, f'Total de registros: {len(providers)}', ln=True)
    pdf.ln(4)

    # --- Encabezado de la tabla ---
    col_widths = [38, 28, 62, 30, 36, 36, 22, 25]
    headers = ['RTN', 'RIF', 'Razon Social', 'Categoria', 'Estado', 'Municipio', 'Estatus', 'Vence']

    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_line_width(0)

    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align='C')
    pdf.ln()

    # --- Filas de datos ---
    pdf.set_font('Helvetica', '', 8)
    fill = False
    STATUS_COLORS = {
        'activo':  (220, 252, 231),
        'vencido': (254, 226, 226),
        'tramite': (254, 249, 195),
    }

    for p in providers:
        # Verificar salto de página antes de dibujar la fila
        pdf.set_text_color(50, 50, 50)
        bg = STATUS_COLORS.get(p.status, (255, 255, 255))
        pdf.set_fill_color(*bg if p.status == 'activo' else (248, 250, 252))

        row_fill = fill
        # Alternar color de fila
        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        fill = not fill

        vence_str = p.valid_until.strftime('%d/%m/%Y') if p.valid_until else 'S/F'
        estado_str = p.municipality.state.name if p.municipality and p.municipality.state else '-'
        muni_str = p.municipality.name if p.municipality else '-'
        cat_str = p.category.name if p.category else '-'

        cells = [p.num_rtn, p.rif, p.razon_social, cat_str, estado_str, muni_str, p.status.upper(), vence_str]
        for i, val in enumerate(cells):
            pdf.cell(col_widths[i], 7, str(val)[:30], border=1, fill=row_fill, align='L')
        pdf.ln()

    return pdf


@reports_bp.route('/rtn')
@login_required
@gerente_or_admin_required
def rtn():
    """Página de descarga de reportes con filtros."""
    categories = Category.query.order_by(Category.name).all()
    states = State.query.order_by(State.name).all()
    return render_template('reports/rtn.html', categories=categories, states=states)


@reports_bp.route('/rtn/pdf')
@login_required
@gerente_or_admin_required
def rtn_pdf():
    """Genera y descarga el reporte RTN en formato PDF."""
    category_id = request.args.get('category_id', type=int)
    state_id = request.args.get('state_id', type=int)
    status_filter = request.args.get('status', '')

    query = TouristProvider.query

    cat_name = None
    if category_id:
        query = query.filter(TouristProvider.category_id == category_id)
        from models import Category as Cat
        cat = Cat.query.get(category_id)
        cat_name = cat.name if cat else None

    estado_name = None
    if state_id:
        from models import Municipality
        muni_ids = [m.id for m in Municipality.query.filter_by(state_id=state_id).all()]
        query = query.filter(TouristProvider.municipality_id.in_(muni_ids))
        from models import State as St
        st = St.query.get(state_id)
        estado_name = st.name if st else None

    if status_filter in ('activo', 'vencido', 'tramite'):
        query = query.filter(TouristProvider.status == status_filter)

    providers = query.order_by(TouristProvider.razon_social).all()

    pdf = _build_rtn_pdf(providers, categoria=cat_name, estado=estado_name)

    pdf_bytes = pdf.output()
    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    filename = f'reporte_rtn_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
