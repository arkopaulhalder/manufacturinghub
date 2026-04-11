from flask import Blueprint

machine_bp = Blueprint('machine', __name__, url_prefix='/machines')

from . import routes
