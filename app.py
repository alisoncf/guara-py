from flask import Flask
from flask_cors import CORS
from sparqapi import sparqapi_app
from classapi import classapi_app
from acesso import acesso_bp

app = Flask(__name__)
CORS(app)

# Registrar os aplicativos Flask dos serviços
app.register_blueprint(sparqapi_app, url_prefix='/sparqapi')
app.register_blueprint(classapi_app, url_prefix='/classapi')
app.register_blueprint(acesso_bp, url_prefix='/acesso')
if __name__ == '__main__':
    app.run(debug=True, port=5000)

