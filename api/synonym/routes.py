from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('synonym', __name__)


@bp.route('/synonym')
def get_synonym():
    word = request.args.get('word', '').strip()
    if not word:
        return jsonify({"error": "query parameter 'word' is required"}), 400

    service = current_app.config['SYNONYM_SERVICE']
    result = service.lookup(word) 
    return jsonify(result) 


@bp.route('/dictionary')
def get_dictionary():
    service = current_app.config['SYNONYM_SERVICE']
    data = service._repo.get_all()
    entries = [{"word": w, "synonyms": syns} for w, syns in sorted(data.items())]
    return jsonify(entries)


@bp.route('/health')
def health():
    repo = current_app.config['SYNONYM_SERVICE']._repo
    return jsonify({"status": "ok", "entries": repo.entry_count()})
