from flask import Blueprint, jsonify, request
from . import service

bp = Blueprint('poem', __name__)


@bp.route('/poem/analyze', methods=['POST'])
def analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': "field 'text' is required"}), 400
    result = service.analyze(text)
    return jsonify(result)
