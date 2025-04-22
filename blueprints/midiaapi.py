from flask import Blueprint, request, jsonify,current_app
import requests, os
import uuid
# Importe suas funções corretamente
from consultas import get_sparq_obj, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required
from flask import g
midiaapi_app = Blueprint('midiaapi_app', __name__)



@midiaapi_app.route('/list', methods=['GET'])
def listar_arquivos():
    try:
        # Obtendo parâmetros da URL
        objeto_id = request.args.get('objetoId')
        repo = request.args.get('repositorio')

        if not objeto_id:
            return jsonify({"error": "Invalid input", "message": "Expected 'objectId' parameter"}), 400
        if not repo:
            return jsonify({"error": "Invalid input", "message": "Expected 'repository' parameter"}), 400

        
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        objeto_folder = os.path.join(upload_folder, str(objeto_id))
        
        arquivos = []
        if os.path.exists(objeto_folder) and os.path.isdir(objeto_folder):
            arquivos = os.listdir(objeto_folder)
            
        sparql_query = f"""
            PREFIX : <{repo}#>
            SELECT ?a ?s 
            WHERE {{ 
                ?a <http://schema.org/associatedMedia> ?s . 
                FILTER (?a = :{objeto_id})
            }}
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data = {'query': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(repo, headers=headers, data=encoded_data)

        if response.status_code == 200:
            sparql_result = response.json()
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        arquivos_map = {nome: {"nome": nome, "uri": ""} for nome in arquivos}

    # Associar as URIs SPARQL aos arquivos correspondentes
        for item in sparql_result.get("results", {}).get("bindings", []):
            uri = item["s"]["value"]
            nome_arquivo = uri.split("/")[-1]  # Obtém apenas o nome do arquivo da URL
            
            
            #print ('procurando ', nome_arquivo,'em',arquivos_map)
            if nome_arquivo in arquivos_map:
                arquivos_map[nome_arquivo]["uri"] = uri
            else:
                arquivos_map[nome_arquivo] = {"nome": nome_arquivo, "uri": uri}

        # Converter para uma lista
        arquivos_combinados = list(arquivos_map.values())
        #print('combinados',arquivos_combinados)
        return jsonify({
            "arquivos_locais": arquivos,
            "arquivos_sparql": sparql_result,
            "arquivos_combinados": arquivos_combinados,
            "path_folder": objeto_folder,
        })
    
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500
    

def add_relation(objeto_uri, repositorio_uri, target_uri, propriedade, repository):
    try:
        objeto = objeto_uri
        repositorio = repositorio_uri
        target = target_uri
        propriedade = propriedade
        repo = repository
        sparqapi_url = repo+'/'+load_config().get('update')
        sparql_query = f"""{get_prefix()}
        PREFIX : <{repo}#>
        INSERT DATA {{
        {objeto} {propriedade} {target} .
        }}
        """
        print('add relação:',sparql_query, ' no repositório ', sparqapi_url)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto digital adicionado com sucesso", "id": objeto}), 200
        else:
            #print (response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
