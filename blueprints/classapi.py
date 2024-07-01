from flask import Blueprint, request, jsonify
import requests, uuid
from consultas import get_sparq_class, get_prefix  # Importe suas funções corretamente
from config_loader import load_config
from urllib.parse import urlencode

classapi_app = Blueprint('classapi_app', __name__)

@classapi_app.route('/listar_classes', methods=['POST'])
def listar_classes():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'keyword' field"}), 400
        if 'orderby' not in data:
            orderby="class"
        else:
            orderby=data['orderby']
        
        keyword = data['keyword']
        sparqapi_url = load_config().get('class_query_url')
        print(sparqapi_url);
        sparql_query = get_sparq_class().replace('%keyword%', keyword).replace('%orderby%',orderby)
        print(sparql_query)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With':'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)
        print('data->',encoded_data)
        response = requests.post(sparqapi_url, headers=headers,data=encoded_data)
        print ('response: ',response)

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
        required_fields = ['label', 'comment', 'parentClass']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        
        # Utilizando o próprio nome da classe como identificador na URI
        nome_classe=data['label'].replace(" ","_")
        
        class_uri = f'http://200.137.241.247:8080/fuseki/mplclass/{nome_classe}'
        sparqapi_url = load_config().get('class_update_url')  # Ajuste para carregar a URL do endpoint SPARQL
        
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>

            INSERT DATA {{
                <{class_uri}> rdf:type owl:Class ;
                                rdfs:label "{data['label']}" ;
                                rdfs:comment "{data['comment']}" ;
                                cmgc:hasParentClass cmgc:{data['parentClass']} .
            }}
        """

        # Exibindo a query SPARQL para depuração
        print(sparql_query)

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)
        print(encoded_data)
        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

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