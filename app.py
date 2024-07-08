from flask import Flask
from flask_cors import CORS
from sparqapi import sparqapi_app
from blueprints.classapi import classapi_app
from blueprints.objectapi import objectapi_app
from blueprints.acesso import acessoapp
import ssl
import requests
from urllib3.exceptions import InsecureRequestWarning

app = Flask(__name__)
CORS(app)

# Registrar os aplicativos Flask dos serviços
app.register_blueprint(sparqapi_app, url_prefix='/sparqapi')
app.register_blueprint(classapi_app, url_prefix='/classapi')
app.register_blueprint(objectapi_app, url_prefix='/objectapi')
app.register_blueprint(acessoapp, url_prefix='/acesso')

if __name__ == '__main__':
    # Desativar os avisos de requisições inseguras (opcional)
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Configurar o contexto SSL
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('C:/home/certificado/cert.pem',
                            'C:/home/certificado/key.pem')

    try:
        # Rodar o app Flask com suporte a HTTPS
        app.run(debug=True, port=5000, ssl_context=context)
    except Exception as e:
        print(f"Erro ao executar o aplicativo Flask: {str(e)}")
