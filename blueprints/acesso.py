from flask import Blueprint, request, jsonify
import requests
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
acessoapp = Blueprint('acessoapp', __name__)


def load_config(filename):
    with open(filename, 'r') as f:
        return json.load(f)


config = load_config('config.json')

FUSEKI_URL = config.get('user_update_url')
FUSEKI_QUERY_URL = config.get('user_query_url')


def execute_sparql_update(query):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data_envio = {'update': query}
    encoded_data = urlencode(data_envio)
    response = requests.post(FUSEKI_URL, headers=headers, data=encoded_data)
    return response


def execute_sparql_query(query):
    headers = {'Accept': 'application/sparql-results+json'}
    response = requests.get(FUSEKI_QUERY_URL, params={
                            'query': query}, headers=headers)
    return response.json()


@acessoapp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    prefix :      <http://guara.ueg.br/ontologias/usuarios#> 
    SELECT ?s ?permissao ?username WHERE {{
        ?s foaf:mbox "{email}" ;
           foaf:password "{password}" .
           ?s :temPermissao ?permissao.
           ?s :username ?username
    }}
    """
    print(query)
    results = execute_sparql_query(query)
    user_data = results['results']['bindings'][0]
    user_uri = user_data['s']['value']
    user_permission = user_data['permissao']['value']
    user_name = user_data['username']['value']

    # Gerar token de autenticação
    token = str(uuid.uuid4())
    validade = datetime.now() + timedelta(hours=24)  # Token válido por 24 horas

    # Atualizar RDF com token e validade
    update = f"""
    PREFIX : <http://guara.ueg.br/ontologia/usuarios#>
    DELETE {{ <{user_uri}> :token ?old_token ; :validade ?old_validade }}
    INSERT {{ <{user_uri}> :token "{token}" ; :validade "{validade.isoformat()}"}}
    WHERE {{
        OPTIONAL {{ <{user_uri}> :token ?old_token }}
        OPTIONAL {{ <{user_uri}> :validade ?old_validade }}
    }}
    """
    print(update)
    response = execute_sparql_update(update)
    if response.status_code != 200:
        return jsonify({'message': 'Failed to update token and validade'}), 500

    return jsonify({
        'message': 'Login successful',
        'user': user_name,
        'email': email,
        'permissao': user_permission,
        'token': token,
        'validade': validade.isoformat()
    }), 200


@acessoapp.route('/add_user', methods=['POST'])
def add_curador():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    permissao = data.get('permissao')

    update = f"""
    PREFIX : <http://guara.ueg.br/ontologia/usuarios#>
    INSERT DATA {{
        :{username} rdf:type :Curador ;
                   :username "{username}" ;
                   :password "{password}" ;
                   :temPermissao "{permissao}" .
    }}
    """
    response = execute_sparql_update(update)
    if response.status_code == 200:
        return jsonify({'message': 'Curador added successfully'}), 201
    else:
        return jsonify({'message': 'Failed to add curador'}), 500
