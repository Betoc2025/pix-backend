

import os
from flask import Flask, send_from_directory, request
from flask_cors import CORS
from models.user import db
from routes.user import user_bp
from routes.pix import pix_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Configurar CORS para permitir Authorization corretamente
CORS(app,
     origins="*",
     allow_headers="*",
     expose_headers="*",
     supports_credentials=True)

# Registrar blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(pix_bp, url_prefix='/api/pix')

# Configuração do banco de dados SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# Rota principal para servir arquivos estáticos
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

# Middleware de logging de requisições (para debug)
@app.before_request
def log_request_info():
    if app.debug:
        print(f"Request: {request.method} {request.url}")
        if request.is_json:
            print(f"JSON: {request.get_json()}")

@app.after_request
def log_response_info(response):
    if app.debug:
        print(f"Response: {response.status_code}")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
