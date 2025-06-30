from flask import Flask, jsonify
from flask_cors import CORS
from flasgger import Swagger
import ssl
import os
from dotenv import load_dotenv
import logging

from sparqapi import sparqapi_app
from blueprints.classapi import classapi_app
from blueprints.objectapi import objectapi_app
from blueprints.acesso import acessoapp
from blueprints.repositorios import repo_app
from blueprints.upload import uploadapp
from blueprints.dimapi import dimapi_app
from blueprints.midiaapi import midiaapi_app
from blueprints.relationapi import relationapi_app
from blueprints.graph_api import graph_api_app  # <<< ADICIONE ESTA LINHA

load_dotenv()


def create_app(config_name=None):
    app = Flask(__name__)

    logging.basicConfig(level=logging.DEBUG if os.getenv('FLASK_ENV') == 'development' else logging.INFO)
    app.logger.info("A iniciar a aplicação Guara-Py...")

    app.config['SWAGGER'] = {
        'openapi': '3.0.2',
        'title': 'Guará API - Documentação',
        'version': '1.0.0',
        'description': 'API para o sistema Guará, permitindo interações com repositórios RDF e ontologias.',
        'uiversion': 3,
        'specs_route': "/apidocs/",
        'components': {
            'securitySchemes': {
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                    'description': "Token de autenticação JWT. Use o formato: Bearer {token}"
                }
            },
            'schemas': {
                'MediaSparqlInfo': {
                    'type': 'object',
                    'properties': {
                        'media_uri': {'type': 'string', 'format': 'uri',
                                      'example': 'http://example.org/media/componenteA.jpg',
                                      'description': 'URI da mídia conforme registrada no SPARQL.'},
                        'objeto_associado_uri': {'type': 'string', 'format': 'uri',
                                                 'example': 'http://localhost:3030/meu_dataset#objfisico-789-uuid-012',
                                                 'description': 'URI do objeto ao qual a mídia está associada.'}
                    },
                    'description': 'Informação de mídia obtida do SPARQL.'
                },
                'ArquivoCombinadoInfo': {
                    'type': 'object',
                    'properties': {
                        'nome_arquivo_local': {'type': 'string', 'example': 'componenteA.jpg',
                                               'description': 'Nome do arquivo encontrado localmente.'},
                        'uri_sparql_correspondente': {'type': 'string', 'format': 'uri', 'nullable': True,
                                                      'example': 'http://example.org/media/componenteA.jpg',
                                                      'description': 'URI da mídia no SPARQL que corresponde ao arquivo local (se houver).'},
                        'presente_localmente': {'type': 'boolean',
                                                'description': 'Indica se o arquivo foi encontrado na pasta de uploads.'},
                        'presente_sparql': {'type': 'boolean',
                                            'description': 'Indica se uma URI correspondente foi encontrada no SPARQL.'}
                    },
                    'description': 'Informação combinada de arquivos locais e SPARQL.'
                }
            }
        }
    }
    swagger = Swagger(app)

    CORS(app, resources={r"/*": {"origins": "*"}})
    app.logger.info("CORS configurado para permitir todas as origens.")

    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', '/var/www/imagens_guara')
    app.config['MEDIA_BASE_URL'] = os.getenv('MEDIA_BASE_URL', '/media')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    app.logger.info(f"Pasta de Upload configurada para: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(f"URL base para mídias: {app.config['MEDIA_BASE_URL']}")

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            app.logger.info(f"Pasta de upload criada em: {app.config['UPLOAD_FOLDER']}")
        except OSError as e:
            app.logger.error(f"Não foi possível criar a pasta de upload {app.config['UPLOAD_FOLDER']}: {e}")

    app.register_blueprint(sparqapi_app, url_prefix='/sparqapi')
    app.register_blueprint(classapi_app, url_prefix='/classapi')
    app.register_blueprint(objectapi_app, url_prefix='/fis')
    app.register_blueprint(acessoapp, url_prefix='/acesso')
    app.register_blueprint(repo_app, url_prefix='/repositorios')
    app.register_blueprint(uploadapp, url_prefix='/uploadapi')
    app.register_blueprint(dimapi_app, url_prefix='/dim')
    app.register_blueprint(midiaapi_app, url_prefix='/midias')
    app.register_blueprint(relationapi_app, url_prefix='/relation')
    app.register_blueprint(graph_api_app, url_prefix='/graph')  # <<< ADICIONE ESTA LINHA
    app.logger.info("Blueprints registados.")

    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok", "message": "Serviço Guará-Py está operacional."}), 200

    return app


if __name__ == '__main__':
    app = create_app()

    environment = os.getenv('FLASK_ENV', 'production')
    cert_path = os.getenv('SSL_CERT_PATH', 'C:/home/certificado/cert.pem')
    key_path = os.getenv('SSL_KEY_PATH', 'C:/home/certificado/key.pem')
    use_ssl = os.getenv('USE_SSL', 'true').lower() == 'true'
    port = int(os.getenv('PORT', 5000))

    app.logger.info(f"Ambiente Flask: {environment}")
    app.logger.info(f"A executar na porta: {port}")

    if environment == 'development':
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        if use_ssl:
            if os.path.exists(cert_path) and os.path.exists(key_path):
                app.logger.info(f"A utilizar SSL com certificado: {cert_path} e chave: {key_path}")
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                try:
                    context.load_cert_chain(cert_path, key_path)
                    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=False)
                except ssl.SSLError as e:
                    app.logger.error(f"Erro ao carregar certificados SSL: {e}. A executar sem SSL.")
                    app.run(host='0.0.0.0', port=port, debug=False)
                except Exception as e:
                    app.logger.error(f"Erro ao executar o aplicativo Flask com SSL: {str(e)}")
                    app.run(host='0.0.0.0', port=port, debug=False)
            else:
                app.logger.warning(
                    f"Certificados SSL não encontrados em '{cert_path}' ou '{key_path}'. A executar sem SSL.")
                app.run(host='0.0.0.0', port=port, debug=False)
        else:
            app.logger.info("SSL não ativado (USE_SSL não é 'true'). A executar sem SSL.")
            app.run(host='0.0.0.0', port=port, debug=False)
