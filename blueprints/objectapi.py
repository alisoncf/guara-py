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
        #print(data)
        # Validar os campos obrigatórios
        required_fields = ['descricao', 'titulo', 'resumo','colecao']
                
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        object_id = str(uuid.uuid4())
        schema = load_config().get('schema_objetos')
        objeto_uri = f"{schema}/{object_id}"
        sparqapi_url = load_config().get('object_update_url')

        
        tem_relacao_part = f':temRelacao {", ".join(f"<{relacao}>" for relacao in data["temRelacao"])}' if "temRelacao" in data and data["temRelacao"] else ''
        associated_media_part = f'schema:associatedMedia {", ".join(f"<{url}>" for url in data["associatedMedia"])}' if "associatedMedia" in data and data["associatedMedia"] else ''
        colecao_part = f':colecao "{data["colecao"]}"' if "colecao" in data and data["colecao"] else ''
        tipo_fisico_part = f':tipoFisico {", ".join(f":{tipo}" for tipo in data["tipoFisico"])}' if "tipoFisico" in data and data["tipoFisico"] else ''

        print (tipo_fisico_part)
        # Montando a lista de partes da query
        parts = [
            f'dc:description "{data["descricao"]}"',
            f'dc:abstract "{data["resumo"]}"',
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
            INSERT DATA {{
                <{objeto_uri}> rdf:type :ObjetoDigital ;
                                { ' ;\n'.join(parts) } .
            }}
        """

        print('->', sparql_query)  # Debugging
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
