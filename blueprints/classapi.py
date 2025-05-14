from flask import Blueprint, request, jsonify
import requests
from consultas import get_sparq_class, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from config_loader import load_config
classapi_app = Blueprint('classapi_app', __name__)


@classapi_app.route('/list', methods=['POST','GET'])
def list():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'keyword' field"}), 400
        if 'repository' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if data['repository']=='' :
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if 'orderby' not in data:
            orderby = "class"
        else:
            orderby = data['orderby']

        

        keyword = data['keyword']
        repo = data['repository']
        #sparqapi_url = load_config().get('class_query_url')
        sparqapi_url = repo

        sparql_query = get_sparq_class().replace(
            '%keyword%', keyword).replace('%orderby%', orderby)
        #print(sparql_query)
        headers = {'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8",
                   'Accept': "application/sparql-results+json,*/*;q=0.9",
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)
        if response.status_code == 200:
            result = response.json()
            
            return jsonify(result)
        else:
            print('erro:',response.text)
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
        required_fields = ['label', 'comment', 'subclassof', 'repository']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        repo = data['repository']
        nome_classe = data['label'].replace(" ", "_")

        #prefix_base = load_config().get('prefix_base_class')
        #class_uri = prefix_base+nome_classe
        #sparqapi_url = load_config().get('class_update_url')
        
        prefix_base = repo+"#"
        class_uri =':'+nome_classe
        sparqapi_url = repo

        comment = data['comment'].replace('"""', '\\"""')  # evita quebra de string SPARQL

        mae = data['subclassof']
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
            PREFIX : <{prefix_base}>
            INSERT DATA {{
                {class_uri} rdf:type owl:Class ;
                                rdfs:label "{data['label']}" ;
                                rdfs:comment \"\"\"{comment}\"\"\" ;
                                rdfs:subClassOf :{mae} .
            }}
        """
        print(sparql_query)

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': "application/sparql-results+json,*/*;q=0.9",
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

@classapi_app.route('/alterar_classe', methods=['POST'])
def alterar_classe():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['label', 'comment', 'subclassof', 'repository']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        
        repo = data['repository']
        nome_classe = data['label'].replace(" ", "_")
        prefix_base = repo  + "#"
        class_uri = f":{nome_classe}"
        sparqapi_url = repo

        mae = data['subclassof']
        
        # Query SPARQL para atualizar os dados da classe existente
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
            PREFIX : <{prefix_base}>

            DELETE WHERE {{
                {class_uri} rdfs:label ?oldLabel ;
                              rdfs:comment ?oldComment ;
                              rdfs:subClassOf ?oldSubclass .
            }};
            
            INSERT DATA {{
                {class_uri} rdf:type owl:Class ;
                              rdfs:label "{data['label']}" ;
                              rdfs:comment "{data['comment']}" ;
                              rdfs:subClassOf :{mae} .
            }}
        """
        
        

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': "application/sparql-results+json,*/*;q=0.9",
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Classe alterada com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500



@classapi_app.route('/excluir_classe', methods=['DELETE','POST'])
def excluir_classe():
    try:
        data = request.get_json()
        required_fields = ['label','repository']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        class_uri = data['label']
        repo = data['repository']
        if verificar_existencia_classe(class_uri,repo):
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
  
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_delete_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response_delete = requests.post(
            repo, headers=headers, data=encoded_data)

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


def verificar_existencia_classe(class_uri,repository_url):
    sparqapi_url = repository_url

    # Montagem da query SPARQL de verificação
    sparql_check_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        ASK {{
            ?s rdfs:subClassOf <{class_uri}> .
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
