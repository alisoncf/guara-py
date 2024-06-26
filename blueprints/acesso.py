from flask import Blueprint, request, jsonify
import requests, json

acesso_bp = Blueprint('acesso', __name__)

def load_config(filename):
    with open(filename, 'r') as f:
        return json.load(f)

config = load_config('config.json')

FUSEKI_URL = config.get('user_update_url')
FUSEKI_QUERY_URL = 'user_query_url'

def execute_sparql_update(query):
    headers = {'Content-Type': 'application/sparql-update'}
    response = requests.post(FUSEKI_URL, data=query, headers=headers)
    return response

def execute_sparql_query(query):
    headers = {'Accept': 'application/sparql-results+json'}
    response = requests.get(FUSEKI_QUERY_URL, params={'query': query}, headers=headers)
    return response.json()

@acesso_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    query = f"""
    PREFIX : <http://example.org/guara#>
    SELECT ?s WHERE {{
        ?s :username "{username}" ;
           :password "{password}" .
    }}
    """
    results = execute_sparql_query(query)
    if results['results']['bindings']:
        return jsonify({'message': 'Login successful', 'user': username}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@acesso_bp.route('/curadores', methods=['POST'])
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
