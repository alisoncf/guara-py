from flask import Blueprint, request, jsonify
import requests
from consultas import get_sparq_class, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from config_loader import load_config
classapi_app = Blueprint('classapi_app', __name__)


@classapi_app.route('/listar_classes', methods=['POST'])
def listar_classes():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'keyword' field"}), 400
        if 'orderby' not in data:
            orderby = "class"
        else:
            orderby = data['orderby']

        keyword = data['keyword']
        sparqapi_url = load_config().get('class_query_url')

        sparql_query = get_sparq_class().replace(
            '%keyword%', keyword).replace('%orderby%', orderby)

        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

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


@classapi_app.route('/adicionar_classe', methods=['POST'])
def adicionar_classe():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['label', 'comment', 'subclassof']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        nome_classe = data['label'].replace(" ", "_")

        prefix_base = load_config().get('prefix_base_class')
        class_uri = prefix_base+nome_classe

        sparqapi_url = load_config().get('class_update_url')
        mae = data['subclassof']
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
            PREFIX : <{prefix_base}>
            INSERT DATA {{
                <{class_uri}> rdf:type owl:Class ;
                                rdfs:label "{data['label']}" ;
                                rdfs:comment "{data['comment']}" ;
                                rdfs:subClassOf :{mae} .
            }}
        """
        print('uri', class_uri)
        print('q', sparql_query)

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Classe adicionada com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@classapi_app.route('/excluir_classe', methods=['DELETE'])
def excluir_classe():
    try:

        data = request.get_json()

        # Validar o campo obrigatório
        required_fields = ['label']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        class_uri = data['label']

        if verificar_existencia_classe(class_uri):
            return jsonify({"error": "Classe não pode ser excluída", "message": "Existem registros relacionados a essa classe"}), 400

        sparqapi_url = load_config().get('class_update_url')

        # Montagem da query SPARQL de deleção
        sparql_delete_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
            PREFIX : <http://200.137.241.247:8080/fuseki/mplclass#>
            DELETE WHERE {{
                <{class_uri}> ?p ?o .
            }}
        """

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_delete_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response_delete = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response_delete.status_code == 200:
            return jsonify({"message": "Classe excluída com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response_delete.status_code, "message": response_delete.text}), response_delete.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


def verificar_existencia_classe(class_uri):
    sparqapi_url = load_config().get('class_query_url')

    # Montagem da query SPARQL de verificação
    sparql_check_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
        PREFIX : <http://200.137.241.247:8080/fuseki/mplclass#>
        ASK {{
            ?s rdfs:subClassOf <class_uri> .
        }}
    """

    # Preparação dos headers e dados para a requisição GET
    headers = {
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    params = {'query': sparql_check_query}

    # Enviar a query SPARQL para verificar a existência de triplas
    response = requests.get(sparqapi_url, headers=headers, params=params)

    if response.status_code == 200:
        result = response.json()
        return result['boolean']
    else:
        raise Exception(
            f"SPARQL query failed: {response.status_code} {response.text}")
