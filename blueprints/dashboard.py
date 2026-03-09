from flask import Blueprint, render_template
from flask_login import login_required
from models import TouristProvider, Category, State, Municipality, db
from sqlalchemy import func
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_providers = TouristProvider.query.count()
    
    # Stats by category
    stats_by_category = db.session.query(
        Category.name, 
        func.count(TouristProvider.id).label('count')
    ).join(TouristProvider).group_by(Category.name).all()
    
    # Stats by status
    stats_by_status = {
        'activo': TouristProvider.query.filter_by(status='activo').count(),
        'vencido': TouristProvider.query.filter_by(status='vencido').count(),
        'tramite': TouristProvider.query.filter_by(status='tramite').count(),
    }
    
    # Stats by state
    stats_by_state = db.session.query(
        State.name,
        func.count(TouristProvider.id).label('count')
    ).join(Municipality, State.id == Municipality.state_id)\
     .join(TouristProvider, Municipality.id == TouristProvider.municipality_id)\
     .group_by(State.name).all()
    
    # Alerts
    today = datetime.utcnow().date()
    thirty_days_later = today + timedelta(days=30)
    
    expiring_soon_list = TouristProvider.query.filter(
        TouristProvider.status == 'activo',
        TouristProvider.valid_until <= thirty_days_later,
        TouristProvider.valid_until >= today
    ).order_by(TouristProvider.valid_until.asc()).limit(5).all()
    
    expiring_soon_count = TouristProvider.query.filter(
        TouristProvider.status == 'activo',
        TouristProvider.valid_until <= thirty_days_later,
        TouristProvider.valid_until >= today
    ).count()
    
    expired_list = TouristProvider.query.filter(
        TouristProvider.status == 'vencido',
        TouristProvider.valid_until < today
    ).order_by(TouristProvider.valid_until.desc()).limit(5).all()
    
    expired_count = TouristProvider.query.filter(
        TouristProvider.status == 'vencido',
        TouristProvider.valid_until < today
    ).count()

    return render_template('dashboard.html', 
                           total_providers=total_providers,
                           stats_by_category=stats_by_category,
                           stats_by_status=stats_by_status,
                           stats_by_state=stats_by_state,
                           expiring_soon_list=expiring_soon_list,
                           expiring_soon_count=expiring_soon_count,
                           expired_list=expired_list,
                           expired_count=expired_count)
