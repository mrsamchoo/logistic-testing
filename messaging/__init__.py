from flask import Blueprint

messaging_bp = Blueprint("messaging", __name__)

from messaging import routes_api  # noqa: E402, F401
from messaging import routes_webhooks  # noqa: E402, F401
