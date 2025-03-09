from flask import Blueprint
from flask_restx import Api

api_bp = Blueprint('api', __name__, url_prefix='/api')
api = Api(
    api_bp,
    version='1.0',
    title='Monzo Credit Card Pot Sync API',
    description='API for managing Monzo and credit card integrations',
    doc='/docs'
)

# Import and register API namespaces
from app.api.accounts import api as accounts_ns
from app.api.sync import api as sync_ns

api.add_namespace(accounts_ns)
api.add_namespace(sync_ns)
