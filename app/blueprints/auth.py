from functools import wraps
from flask import request, jsonify
from datetime import datetime
from flask import g

# Namespace RDF dos dados de usuário: precisa bater com o valor usado
# quando os dados foram inseridos no Fuseki (ver acesso.py), e é FIXO -
# não deve ser confundido com FUSEKI_BASE_URL (o endereço usado para
# CONECTAR no Fuseki, que varia por ambiente).
NAMESPACE_USUARIOS = "https://guara.ueg.br/fuseki/usuarios"


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Import tardio para evitar ciclo de import: acesso.py importa
        # repositorios.py, que importa token_required deste módulo.
        from ..blueprints.acesso import execute_sparql_query

        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token não fornecido'}), 401

        token = token.replace('Bearer ', '')
        query = f"""
        PREFIX : <{NAMESPACE_USUARIOS}#>
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
