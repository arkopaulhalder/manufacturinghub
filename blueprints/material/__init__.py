from flask import Blueprint

material_bp = Blueprint('material', __name__, url_prefix='/materials')

from . import routes
