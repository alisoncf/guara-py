from flask import Blueprint, request, jsonify,current_app
import requests, os
import uuid
# Importe suas funções corretamente
from consultas import get_sparq_all,get_sparq_dim, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required
dimapi_app = Blueprint('dimapi_app', __name__)


@dimapi_app.route('/list', methods=['GET','POST'])
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
        type = data['type']
        
        prefix_base = repo  + "#"
        sparqapi_url = repo
        
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_dim().replace('%keyword%', keyword)
        
        print('query',sparql_query) 
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

@dimapi_app.route('/listall', methods=['GET','POST'])
def list_all():
    try:
        data = request.get_json()
        
        if 'repository' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if data['repository']=='' :
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if 'type' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'type' field"}), 400
        keyword = data['keyword']
        repo = data['repository']
        tipo = data['type']
        

        prefix_base = repo  + "#"
        sparqapi_url = repo
        replace_tipo = {
            'quem': 'a obj:Pessoa;',
            'quando': 'a obj:Tempo;',
            'onde': 'a obj:Lugar;',
            'oque': 'a obj:Evento;',
            'fisico': 'a obj:ObjetoFisico;'
        }.get(tipo, '') 
        
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_all()
        
        try:
            
            sparql_query = sparql_query.replace('%keyword%', keyword)
            
            sparql_query = sparql_query.replace('%tipo%', replace_tipo)
        except Exception as e:
            print('eero',e)

        print('query',sparql_query) 
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

@dimapi_app.route('/listar_arquivos', methods=['GET'])
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
    
@dimapi_app.route('/create', methods=['POST'])
@token_required
def create():
    try:
        data = request.get_json()
        required_fields = ['descricao', 'titulo', 'resumo','tipo','repository']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        repo = data['repository']
        type = data['tipo']['uri']
        
        object_id = str(uuid.uuid4())
        objeto_uri = f":{object_id}"

        coordenadas = data['coordenadas']
        coord=''
        if coordenadas:
            lat, lon = coordenadas.split(',')
            lat = lat.strip()
            lon = lon.strip()
            coord = f'geo:lat "{lat}";geo:lon "{lon}";'
            
        sparqapi_url = repo+'/'+load_config().get('update')
       
        
            
        tem_relacao_part = f':temRelacao {", ".join(f"<{relacao}>" for relacao in data["temRelacao"])}' if "temRelacao" in data and data["temRelacao"] else ''
        associated_media_part = f'schema:associatedMedia {", ".join(f"<{url}>" for url in data["associatedMedia"])}' if "associatedMedia" in data and data["associatedMedia"] else ''
        
        descricao = '"""' + data["descricao"].replace('"""', '\\"""') + '"""'
        resumo = '"""' + data["resumo"].replace('"""', '\\"""') + '"""'
        titulo = '"""' + data["titulo"].replace('"""', '\\"""') + '"""'
        # Montando a lista de partes da query
        parts = [
            f'dc:description {descricao}',
            f'dc:abstract {resumo}',
            f'dc:title {titulo}',
            tem_relacao_part,
            associated_media_part,
        ]

        # Remover partes vazias (strings vazias ou espaços em branco)
        parts = [part for part in parts if part.strip()]

        # Construção final da query SPARQL
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            INSERT DATA {{
                {objeto_uri} rdf:type <{type}> ;
                rdf:type obj:ObjetoDimensional ;
                {coord}
                obj:dimensao <{type}> ;
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



@dimapi_app.route('/delete', methods=['DELETE','POST'])
@token_required
def excluir():
    try:
        data = request.get_json()

        if "id" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' and 'repository' fields"}), 400
        
        repo = data["repository"]
        objeto_id = data["id"]
        #print(objeto_id)
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
    
@dimapi_app.route('/remover_relacao', methods=['DELETE'])
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
    

@dimapi_app.route('/update', methods=['PUT', 'POST'])
@token_required
def update():
    try:
        data = request.get_json()
        
        # Validação básica dos campos obrigatórios
        required_fields = ['descricao', 'titulo', 'resumo', 'id', 'repository', 'tipo']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        # Captura dos dados
        repo = data['repository']
        description = data['descricao']
        abstract = data['resumo']
        titulo = data['titulo']
        object_id = data['id']
        objeto_uri = f":{object_id}"
        sparqapi_url = repo + '/' + load_config().get('update')
        coordenadas = data.get('coordenadas', None)

        # Começa a construir o bloco SPARQL
        delete_block = f"""
            {objeto_uri} dc:description ?oldDescription ;
                        dc:title ?oldTitle ;
                        dc:abstract ?oldAbstract .
        """

        insert_block = f"""
            {objeto_uri} 
                dc:description \"\"\"{description}\"\"\";
                dc:abstract \"\"\"{abstract}\"\"\";
                dc:title \"\"\"{titulo}\"\"\" ;
        """

        where_block = f"""
            OPTIONAL {{ {objeto_uri} dc:description ?oldDescription . }}
            OPTIONAL {{ {objeto_uri} dc:title ?oldTitle . }}
            OPTIONAL {{ {objeto_uri} dc:abstract ?oldAbstract . }}
        """

        # Se coordenadas existirem, adiciona no bloco SPARQL
        if coordenadas:
            try:
                lat, lon = coordenadas.split(',')
                lat = lat.strip()
                lon = lon.strip()

                delete_block += f"""
                    {objeto_uri} geo:lat ?oldLat ;
                                geo:long ?oldLong .
                """
                insert_block += f"""
                    geo:lat \"\"\"{lat}\"\"\" ;
                    geo:long \"\"\"{lon}\"\"\" .
                """
                where_block += f"""
                    OPTIONAL {{ {objeto_uri} geo:lat ?oldLat . }}
                    OPTIONAL {{ {objeto_uri} geo:long ?oldLong . }}
                """
            except ValueError:
                print("Coordenadas mal formatadas. Ignorando coordenadas.")

        # Finaliza SPARQL
        sparql_query = f"""{get_prefix()}
PREFIX : <{repo}#>

DELETE {{
    {delete_block}
}}
INSERT {{
    {insert_block}
}}
WHERE {{
    {where_block}
}}
"""

        print('SPARQL UPDATE:', sparql_query)

        # Headers e envio da requisição
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto atualizado com sucesso", "id": object_id}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@dimapi_app.route('/update_old', methods=['PUT','POST'])
@token_required
def update_old():
    try:
        data = request.get_json()
        
        if "id" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' field"}), 400

        required_fields = ['descricao', 'titulo', 'resumo','id','repository','tipo']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        
        repo = data['repository']
        description=data['descricao']
        abstract=data['resumo']
        titulo=data['titulo']
        object_id = data['id']
        objeto_uri = f":{object_id}"
        sparqapi_url = repo+'/'+load_config().get('update')
        coordenadas = data['coordenadas']
        

        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE {{
                {objeto_uri} dc:description ?oldDescription; dc:title ?oldTitle  ;
                dc:title ?oldTitle  ;
                dc:abstract ?oldAbstract.
            }}
            INSERT {{
                {objeto_uri} 
                    dc:description "{description}";
                    dc:abstract "{abstract}";
                    dc:title "{titulo}" .
            }}
            WHERE {{
                {objeto_uri}  dc:title ?oldTitle ;
                dc:description ?oldDescription ;
                dc:abstract ?oldAbstract.
            }}
        """
        print('update',sparql_query)   
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

        #return jsonify({"message": "Nenhuma alteração enviada"}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500
    

@dimapi_app.route('/add_relation', methods=['POST'])
@token_required
def add_relation():
    try:
        data = request.get_json()
        objeto = data["o"]
        repositorio = data["repositorio_uri"]
        midia = data["midia_uri"]
        propriedade = data["propriedade"]
        repo = data['repository']
        sparqapi_url = repo+'/'+load_config().get('update')
        sparql_query = f"""{get_prefix()}
        PREFIX : <{repo}#>
        INSERT DATA {{
        {objeto} {propriedade} {midia} .
        }}
        """
        #print('add relação:',sparql_query, ' no repositório ', sparqapi_url)
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
