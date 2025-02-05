from flask import Flask
from flask_cors import CORS
from sparqapi import sparqapi_app
from blueprints.classapi import classapi_app
from blueprints.objectapi import objectapi_app
from blueprints.acesso import acessoapp
from blueprints.repositorios import repo_app
from blueprints.upload import uploadapp
import ssl
import os
from dotenv import load_dotenv
import requests
from urllib3.exceptions import InsecureRequestWarning

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()





app = Flask(__name__)
CORS(app)
CORS(app, resources={r"/*": {"origins": ["https://localhost:9000"]}})


app.config['UPLOAD_FOLDER'] = '/arquivos/upload'

# Outras configurações (opcional)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB por arquivo
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif', 'mp4'}  # Extensões permitidas




# Registrar os aplicativos Flask dos serviços
app.register_blueprint(sparqapi_app, url_prefix='/sparqapi')
app.register_blueprint(classapi_app, url_prefix='/classapi')
app.register_blueprint(objectapi_app, url_prefix='/objectapi')
app.register_blueprint(acessoapp, url_prefix='/acesso')
app.register_blueprint(repo_app, url_prefix='/repositorios')
app.register_blueprint(uploadapp, url_prefix='/uploadapp')

if __name__ == '__main__':
    # Desativar os avisos de requisições inseguras (opcional)
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Detectar ambiente
    environment = os.getenv('FLASK_ENV', 'production')

    if environment == 'development':
        # Rodar o app Flask com suporte a HTTP (desenvolvimento)
        app.run(debug=True, port=5000)
    else:
        # Configurar o contexto SSL (produção)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('C:/home/certificado/cert.pem',
                                'C:/home/certificado/key.pem')
        try:
            # Rodar o app Flask com suporte a HTTPS (produção)
            app.run(debug=True, port=5000, ssl_context=context)
        except Exception as e:
            print(f"Erro ao executar o aplicativo Flask: {str(e)}")
