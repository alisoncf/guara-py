from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flasgger import Swagger
import os, ssl, requests
from urllib3.exceptions import InsecureRequestWarning

# Blueprints
from app.sparqapi import sparqapi_app
from app.blueprints.classapi import classapi_app
from app.blueprints.objectapi import objectapi_app
from app.blueprints.acesso import acessoapp
from app.blueprints.repositorios import repo_app
from app.blueprints.upload import uploadapp
from app.blueprints.dimapi import dimapi_app
from app.blueprints.midiaapi import midiaapi_app
from app.blueprints.relationapi import relationapi_app

def create_app():
    load_dotenv()

    app = Flask(__name__)
    Swagger(app)
    CORS(app, resources={r"/*": {"origins": ["https://localhost:9000","http://localhost:9000"]}})

    app.config['UPLOAD_FOLDER'] = '/var/www/imagens'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif', 'mp4'}

    # Blueprints
    app.register_blueprint(sparqapi_app, url_prefix='/sparqapi')
    app.register_blueprint(classapi_app, url_prefix='/classapi')
    app.register_blueprint(objectapi_app, url_prefix='/fis')
    app.register_blueprint(acessoapp, url_prefix='/acesso')
    app.register_blueprint(repo_app, url_prefix='/repositorios')
    app.register_blueprint(uploadapp, url_prefix='/uploadapi')
    app.register_blueprint(dimapi_app, url_prefix='/dim')
    app.register_blueprint(midiaapi_app, url_prefix='/midias')
    app.register_blueprint(relationapi_app, url_prefix='/relation')

    # Ambiente
    environment = os.getenv('FLASK_ENV', 'production')
    if environment != 'development':
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('C:/home/certificado/cert.pem',
                                'C:/home/certificado/key.pem')
        app.config['SSL_CONTEXT'] = context

    return app
