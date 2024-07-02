from flask import Blueprint, request, jsonify
import requests
import uuid
# Importe suas funções corretamente
from consultas import get_sparq_obj, get_prefix
from config_loader import load_config
from urllib.parse import urlencode

objectapi_app = Blueprint('objectapi_app', __name__)


@objectapi_app.route('/listar_objetos', methods=['POST'])
def listar_objetos_fisicos():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'keyword' field"}), 400

        keyword = data['keyword']
        sparqapi_url = load_config().get('object_query_url')
        sparql_query = get_sparq_obj().replace('%keyword%', keyword)
        print(sparql_query)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)
        print('data->', encoded_data)
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)
        print('response: ', response)

        if response.status_code == 200:
            result = response.json()
            return jsonify(result)
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except TypeError as e:
        return jsonify({"error": "TypeError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@objectapi_app.route('/adicionar_objeto_fisico', methods=['POST'])
def adicionar_objeto_fisico():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['description', 'title',
                           'content_urls', 'depictions', 'physical_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        object_id = str(uuid.uuid4())

        objeto_uri = 'http://200.137.241.247:8080/fuseki/objetos/{object_id}'
        sparqapi_url = load_config().get('object_update_url')

        sparql_query = get_prefix + """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX dc: <http://purl.org/dc/elements/1.1/>
            PREFIX foaf: <http://xmlns.com/foaf/0.1/>
            PREFIX schema: <http://schema.org/>

            INSERT DATA {{
                <{objeto_uri}> rdf:type :ObjetoDigital ;
                                dc:description "{data['description']}" ;
                                dc:title "{data['title']}" ;
                                schema:contentUrl {", ".join(f'<{url}>' for url in data['content_urls'])} ;
                                foaf:depiction {", ".join(f'<{url}>' for url in data['depictions'])} ;
                                :tipoFisico :{data['physical_type']} .
            }}
        """
        print(sparql_query)
        # Enviar a query SPARQL para o endpoint de atualização
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto digital adicionado com sucesso", "id": object_id}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500
