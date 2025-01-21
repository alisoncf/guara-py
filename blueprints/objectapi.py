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
        if 'repository' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if data['repository']=='' :
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        keyword = data['keyword']
        repo = data['repository']
        
        prefix_base = repo  + "#"
        #sparqapi_url = load_config().get('object_query_url')
        sparqapi_url = repo
        
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_obj().replace('%keyword%', keyword)
        
        print(sparql_query) 
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)
        
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)
        #print('response: ', response)

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
        #print(data)
        # Validar os campos obrigatórios
        required_fields = ['descricao', 'titulo', 'resumo','colecao','repository']
          
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        repo = data['repository']
        #tipo_fisico = data['tipoFisicoAbreviado']
        #print(tipo_fisico)
        
        object_id = str(uuid.uuid4())
        colecao = data['colecao'].split('#')[-1] 
        
        objeto_uri = f":{object_id}"
        #sparqapi_url = load_config().get('object_update_url')
        sparqapi_url = repo+'/'+load_config().get('update')
        #print(sparqapi_url)
        
        tem_relacao_part = f':temRelacao {", ".join(f"<{relacao}>" for relacao in data["temRelacao"])}' if "temRelacao" in data and data["temRelacao"] else ''
        associated_media_part = f'schema:associatedMedia {", ".join(f"<{url}>" for url in data["associatedMedia"])}' if "associatedMedia" in data and data["associatedMedia"] else ''
        colecao_part = f'obj:colecao :{colecao}' if "colecao" in data and data["colecao"] else ''
        tipo_fisico_part = f'obj:tipoFisico {", ".join(f"obj:{tipo}" for tipo in data["tipoFisicoAbreviado"])}' if "tipoFisicoAbreviado" in data and data["tipoFisicoAbreviado"] else ''

        #print (tipo_fisico_part)
        # Montando a lista de partes da query
        parts = [
            f'dc:description "{data["descricao"]}"',
            f'dc:subject "{data["resumo"]}"',
            f'dc:title "{data["titulo"]}"',
            colecao_part,
            tem_relacao_part,
            associated_media_part,
            tipo_fisico_part
        ]

        # Remover partes vazias (strings vazias ou espaços em branco)
        parts = [part for part in parts if part.strip()]

        # Construção final da query SPARQL
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            INSERT DATA {{
                {objeto_uri} rdf:type obj:ObjetoFisico ;
                                { ' ;\n'.join(parts) } .
            }}
        """

        #print('->', sparql_query)  # Debugging
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
            print (response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500

@objectapi_app.route('/excluir_objeto_fisico', methods=['DELETE'])
def excluir_objeto_fisico():
    try:
        data = request.get_json()

        if "id" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' and 'repository' fields"}), 400
        
        repo = data["repository"]
        objeto_id = data["id"]
        print(objeto_id)
        objeto_uri = f":{objeto_id}"
        sparqapi_url = f"{repo}/{load_config().get('update')}"
        
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE WHERE {{
                {objeto_uri} ?p ?o .
            }}
        """
        #print (sparql_query)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }

        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto físico excluído com sucesso", "id": objeto_id}), 200
        else:
            print(response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
    

@objectapi_app.route('/atualizar_objeto_fisico', methods=['PUT'])
def atualizar_objeto_fisico():
    try:
        data = request.get_json()

        if "id" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' field"}), 400

        required_fields = ['descricao', 'titulo', 'resumo','colecao','repository']
          
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        repo = data['repository']

        object_id = data["id"]
        objeto_uri = f":{object_id}"
        colecao = data['colecao'].split('#')[-1] 
        
        sparqapi_url = repo + '/' + load_config().get('update')
        tem_relacao_part = f':temRelacao {", ".join(f"<{relacao}>" for relacao in data["temRelacao"])}' if "temRelacao" in data and data["temRelacao"] else ''
        associated_media_part = f'schema:associatedMedia {", ".join(f"<{url}>" for url in data["associatedMedia"])}' if "associatedMedia" in data and data["associatedMedia"] else ''
        colecao_part = f'obj:colecao :{colecao}' if "colecao" in data and data["colecao"] else ''
        tipo_fisico_part = f'obj:tipoFisico {", ".join(f"obj:{tipo}" for tipo in data["tipoFisicoAbreviado"])}' if "tipoFisicoAbreviado" in data and data["tipoFisicoAbreviado"] else ''

        #print (tipo_fisico_part)
        # Montando a lista de partes da query
        parts = [
            f'dc:description "{data["descricao"]}"',
            f'dc:subject "{data["resumo"]}"',
            f'dc:title "{data["titulo"]}"',
            colecao_part,
            tem_relacao_part,
            associated_media_part,
            tipo_fisico_part
        ]

        # Remover partes vazias (strings vazias ou espaços em branco)
        parts = [part for part in parts if part.strip()]

        
        if parts:
            sparql_query = f"""{get_prefix()}
                PREFIX : <{repo}#>
                DELETE {{
                    {objeto_uri} ?p ?o .
                }}
                INSERT {{
                    {objeto_uri} rdf:type obj:ObjetoFisico ;
                        {' ;\n'.join(parts)} .
                }}
                WHERE {{
                    {objeto_uri} ?p ?o .
                }}
            """
            headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
            data = {'update': sparql_query}
            encoded_data = urlencode(data)
            print(sparql_query)    
            response = requests.post(
                sparqapi_url, headers=headers, data=encoded_data)

            
            


            if response.status_code == 200:
                return jsonify({"message": "Objeto atualizado com sucesso", "id": object_id}), 200
            else:
                return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        return jsonify({"message": "Nenhuma alteração enviada"}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500