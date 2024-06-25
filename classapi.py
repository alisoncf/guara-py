from flask import Blueprint, request, jsonify
import requests

classapi_app = Blueprint('classapi_app', __name__)

@classapi_app.route('/listar_classes', methods=['GET'])
def listar_classes():
    sparqapi_url = 'http://localhost:5000/sparqapi/query'

    sparql_query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?classe ?label ?comentario ?classeMae
    WHERE {
        ?classe rdf:type owl:Class .
        ?classe rdfs:label ?label .
        ?classe rdfs:comment ?comentario .
        OPTIONAL { ?classe rdfs:subClassOf ?classeMae }
    }
    """

    params = {'query': sparql_query}

    response = requests.get(sparqapi_url, params=params)

    if response.status_code == 200:
        result = response.json()
        return jsonify(result)
    else:
        return jsonify({"error": response.status_code, "message": response.text})
