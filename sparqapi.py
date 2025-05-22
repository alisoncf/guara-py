from flask import Blueprint, request, jsonify
from flask_cors import CORS
import requests, json

sparqapi_app = Blueprint('sparqapi_app', __name__)
CORS(sparqapi_app)

def load_config1(filename):
    with open(filename, 'r') as f:
        return json.load(f)

config = load_config1('config.json')

fuseki_update_url = config.get('fuseki_update_url')
fuseki_query_url = config.get('fuseki_query_url')

def execute_update(query):
    headers = {
        "Content-Type": "application/sparql-update"
    }
    response = requests.post(fuseki_update_url, data=query, headers=headers)
    if response.status_code == 200:
        return "Atualização SPARQL realizada com sucesso!"
    else:
        return f"Erro na atualização SPARQL: {response.status_code}\n{response.text}"

def execute_query(query):
    headers = {
        "Accept": "application/sparql-results+json"
    }
    response = requests.get(fuseki_query_url, params={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}

@sparqapi_app.route('/query', methods=['GET'])
def sparql_query():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Faltando parâmetro 'query'"}), 400
    result = execute_query(query)
    return jsonify(result)

@sparqapi_app.route('/update', methods=['POST'])
def sparql_update():
    query = request.data.decode('utf-8')
    if not query:
        return jsonify({"error": "Faltando corpo da requisição com a atualização SPARQL"}), 400
    result = execute_update(query)
    return jsonify({"message": result})
