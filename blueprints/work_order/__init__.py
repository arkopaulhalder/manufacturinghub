from flask import Blueprint

work_order_bp = Blueprint('work_order', __name__, url_prefix='/work-orders')

from . import routes
