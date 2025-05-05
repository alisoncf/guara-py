from flask import Blueprint, request, jsonify,current_app
import requests, os
import uuid
# Importe suas funções corretamente
from consultas import get_sparq_obj, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required
from flask import g
objectapi_app = Blueprint('objectapi_app', __name__)


@objectapi_app.route('/list', methods=['POST','GET'])
def list():
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
        sparqapi_url = repo
        
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_obj().replace('%keyword%', keyword)
        
        print('q',sparql_query);
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

@objectapi_app.route('/listar_arquivos', methods=['GET'])
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
    
@objectapi_app.route('/create', methods=['POST'])
@token_required
def create():
    try:
        data = request.get_json()
        required_fields = ['descricao', 'titulo', 'resumo','colecao','repository']
        repo = data['repository']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        
        if data['titulo']=='':
            return jsonify({"error": "Invalid input", "message": "Informe um nome/título"}), 400
        
        object_id = str(uuid.uuid4())
        colecao = data['colecao'].split('#')[-1] 
        

        objeto_uri = f":{object_id}"
        sparqapi_url = repo+'/'+load_config().get('update')
        
        
        tem_relacao_part = f':temRelacao {", ".join(f"<{relacao}>" for relacao in data["temRelacao"])}' if "temRelacao" in data and data["temRelacao"] else ''
        associated_media_part = f'schema:associatedMedia {", ".join(f"<{url}>" for url in data["associatedMedia"])}' if "associatedMedia" in data and data["associatedMedia"] else ''
        colecao_part = f'obj:colecao :{colecao}' if "colecao" in data and data["colecao"] else ''
        tipo_fisico_part = f'obj:tipoFisico {", ".join(f":{tipo}" for tipo in data["tipoFisicoAbreviado"])}' if "tipoFisicoAbreviado" in data and data["tipoFisicoAbreviado"] else ''

        #print (tipo_fisico_part)
        # Montando a lista de partes da query
        descricao = '"""' + data["descricao"].replace('"""', '\\"""') + '"""'
        resumo = '"""' + data["resumo"].replace('"""', '\\"""') + '"""'
        titulo = '"""' + data["titulo"].replace('"""', '\\"""') + '"""'
        parts = [
            f'dc:description {descricao}',
            f'dc:abstract {resumo}',
            f'dc:title {titulo}',
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

@objectapi_app.route('/delete', methods=['DELETE'])
@token_required
def excluir_objeto_fisico():
    
    print("Usuário autenticado:", g.user_uri)
    try:
        data = request.get_json()

        if "id" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' and 'repository' fields"}), 400
        
        repo = data["repository"]
        objeto_id = data["id"]
        
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
            #print(response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
    
@objectapi_app.route('/remover_relacao', methods=['DELETE'])
@token_required
def remover_relacao():
    try:
        data = request.get_json()

        if "s" not in data or "p" not in data or "o" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 's','p','o' and 'repository' fields"}), 400
        
        repo = data["repository"]
        
        s = data["s"]
        p = data["p"]
        o = data["s"]
        
        
        sparqapi_url = f"{repo}/{load_config().get('update')}"
        
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE WHERE {{
                {s} {p} {o} .
            }}
        """
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }

        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "relação excluído com sucessa", "id": '{s} {p} {o}'}), 200
        else:
            #print(response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
    
@objectapi_app.route('/update', methods=['PUT','POST'])
@token_required
def update():
    try:
        data = request.get_json()
        print("Usuário autenticado:", g.user_uri)
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
                
        
        tipo_fisico_part = f'obj:tipoFisico {", ".join(f"obj:{tipo}" for tipo in data["tipoFisicoAbreviado"])}' if "tipoFisicoAbreviado" in data and data["tipoFisicoAbreviado"] else ''
        
        parts = [
            
            tipo_fisico_part
        ]

        # Remover partes vazias (strings vazias ou espaços em branco)
        parts = [part for part in parts if part.strip()]
        descricao = '"""' + data["descricao"].replace('"""', '\\"""') + '"""'
        resumo = '"""' + data["resumo"].replace('"""', '\\"""') + '"""'
        titulo = '"""' + data["titulo"].replace('"""', '\\"""') + '"""'
        if parts:
            sparql_query = f"""{get_prefix()}
                PREFIX : <{repo}#>
                DELETE {{
                    {objeto_uri} dc:description ?oldDescription;
                      dc:abstract ?oldAbstract;
                      dc:title ?oldTitle;
                      obj:tipoFisico ?oldTipo.
                }}
                INSERT {{
                    {objeto_uri} rdf:type obj:ObjetoFisico ;
                        dc:description {descricao};
                        dc:abstract {resumo};
                        dc:title {titulo};
                        {' ;\n'.join(parts)} .
                }}
                WHERE {{
                    {objeto_uri} dc:description ?oldDescription;
                      dc:abstract ?oldAbstract;
                      dc:title ?oldTitle;
                    obj:tipoFisico ?oldTipo.
                }}
            """
            print('#query:',sparql_query)
            headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
            data = {'update': sparql_query}
            encoded_data = urlencode(data)
            
            response = requests.post(
                sparqapi_url, headers=headers, data=encoded_data)

            
            


            if response.status_code == 200:
                return jsonify({"message": "Objeto atualizado com sucesso", "id": object_id}), 200
            else:
                return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        return jsonify({"message": "Nenhuma alteração enviada"}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500
    

@objectapi_app.route('/adicionar_relacao', methods=['POST'])

def adicionar_relacao():
    try:
        data = request.get_json()
        return add_relation(
            objeto_uri=data["objeto_uri"],
            repositorio_uri=data["repositorio_uri"],
            midia_uri=data["midia_uri"],
            propriedade=data["propriedade"],
            repository=data["repository"]
        )
    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

def add_relation(objeto_uri, repositorio_uri, midia_uri, propriedade, repository):
    try:
        objeto = objeto_uri
        repositorio = repositorio_uri
        midia = midia_uri
        propriedade = propriedade
        repo = repository
        sparqapi_url = repo+'/'+load_config().get('update')
        sparql_query = f"""{get_prefix()}
        PREFIX : <{repo}#>
        INSERT DATA {{
        {objeto} {propriedade} {midia} .
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
