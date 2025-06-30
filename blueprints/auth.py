from functools import wraps
from flask import request, jsonify, g, current_app
from datetime import datetime, timezone
# Importar a função execute_sparql_query do módulo utils
from utils import execute_sparql_query
# Importar o carregador de configuração
from config_loader import load_config

# Carregar a configuração uma vez quando o módulo é importado
config = load_config('config.json')
FUSEKI_QUERY_URL = config.get('user_query_url')

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token não fornecido'}), 401

        token = token.replace('Bearer ', '')
        query = f"""
        PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
        SELECT ?user ?validade ?permissao
            WHERE {{
                ?user :token "{token}" ;
                  :validade ?validade ;
                  :temPermissao ?permissao .
        }}
        """
        current_app.logger.debug(f"Buscando token: {query}") # Adicionado log
        try:
            # Usar a variável FUSEKI_QUERY_URL definida globalmente neste módulo
            results = execute_sparql_query(FUSEKI_QUERY_URL, query)
            bindings = results.get('results', {}).get('bindings', [])

            if not bindings:
                return jsonify({'message': 'Token inválido'}), 401

            # Verificar validade do token
            validade_str = bindings[0]['validade']['value']
            # Tratar diferentes formatos de data
            if validade_str.endswith('Z'):
                validade_str = validade_str.replace('Z', '+00:00')
            validade_dt = datetime.fromisoformat(validade_str)

            if datetime.now(timezone.utc) > validade_dt:
                return jsonify({'message': 'Token expirado'}), 403

            g.user_uri = bindings[0]['user']['value']
            return f(*args, **kwargs)
        except Exception as e:
            # Captura as exceções levantadas por execute_sparql_query
            current_app.logger.error(f"Erro ao validar token: {str(e)}")
            if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
                status_code = int(e.args[0].split("status ")[1].split(" ")[0])
                message = e.args[1]
                return jsonify({"error": "SPARQL Query Error", "message": message}), status_code
            elif "Network error" in str(e):
                return jsonify({"error": "Network Error", "message": str(e)}), 500
            else:
                return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return decorated_function
