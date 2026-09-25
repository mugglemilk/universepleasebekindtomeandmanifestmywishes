from flask import Flask, render_template  # 1. นำเข้า render_template แทน send_from_directory
import os
from api.synonym.repository import SynonymRepository
from api.synonym.service import SynonymService
from api.synonym.routes import bp as synonym_bp
from api.poem.routes import bp as poem_bp

def create_app():
    # 2. ใส่ template_folder='frontend' ไว้ตรงนี้ เพื่อบอกตำแหน่งโฟลเดอร์ให้ Flask รู้จัก
    app = Flask(__name__, template_folder='frontend')

    repo = SynonymRepository()
    app.config['SYNONYM_SERVICE'] = SynonymService(repo)

    app.register_blueprint(synonym_bp, url_prefix='/api')
    app.register_blueprint(poem_bp, url_prefix='/api')

    @app.route('/')
    def home():
        # 3. ใช้ render_template เรียกชื่อไฟล์ได้เลย ไม่ต้องใช้ os.path.join หรือ send_from_directory แล้ว
        return render_template('synonym.html')

    @app.route('/dictionary')
    def dictionary():
        return render_template('dictionary.html')

    @app.route('/poem')
    def poem():
        return render_template('poem.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001)