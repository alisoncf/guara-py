from functools import wraps
from flask import request, jsonify
from datetime import datetime
from ..blueprints.acesso import execute_sparql_query  # ou onde estiver
from flask import g
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token não fornecido'}), 401

        token = token.replace('Bearer ', '')
        query = f"""
        PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
        SELECT ?user ?validade  (GROUP_CONCAT(?permissao; separator=", ") AS ?permissoes) 
            WHERE {{
                ?user :token "{token}" ;
                  :validade ?validade ;
                  :temPermissao ?permissao .
            
        }}GROUP BY ?user ?validade
        """
        print('#buscando token:',query)
        results = execute_sparql_query(query)
        bindings = results.get('results', {}).get('bindings', [])

        if not bindings:
            return jsonify({'message': 'Token inválido'}), 403

        validade_str = bindings[0]['validade']['value']
        validade_dt = datetime.fromisoformat(validade_str)

        if datetime.now() > validade_dt:
            return jsonify({'message': 'Token expirado'}), 403
        
        
        g.user_uri = bindings[0]['user']['value']
        return f(*args, **kwargs)
    return decorated_function
