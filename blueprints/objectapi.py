from flask import Blueprint, request, jsonify,current_app, g
import requests, os
import uuid
from consultas import get_sparq_obj, get_prefix # get_prefix é usado implicitamente nas queries
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required # Importar o decorador de token

objectapi_app = Blueprint('objectapi_app', __name__) # Montado em /fis

@objectapi_app.route('/list', methods=['POST','GET'])
def list_physical_objects(): # Renomeado de 'list'
    """
    Lista objetos físicos de um repositório SPARQL com base numa palavra-chave.
    Este endpoint suporta GET (com query parameters) e POST (com JSON body).
    A documentação abaixo foca no método POST. Para GET, use os mesmos parâmetros como query strings.
    ---
    tags:
      - Objetos Físicos
    parameters:
      - name: keyword
        in: query
        required: true # A query get_sparq_obj() usa %keyword%
        description: Palavra-chave para filtrar os objetos físicos (usado se o método for GET).
        schema:
          type: string
        example: "Cadeira"
      - name: repository_sparql_endpoint # Renomeado de 'repository' para clareza
        in: query
        required: true
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:3030/mydataset/sparql"
    requestBody:
      description: Parâmetros para busca de objetos físicos (usado se o método for POST).
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - keyword
              - repository_sparql_endpoint # Renomeado de 'repository'
            properties:
              keyword:
                type: string
                description: Palavra-chave para filtrar os objetos físicos.
                example: "Mesa"
              repository_sparql_endpoint: # Renomeado de 'repository'
                type: string
                format: uri
                description: URL do endpoint SPARQL do repositório.
                example: "http://localhost:3030/mydataset/sparql"
    responses:
      200:
        description: Lista de objetos físicos encontrada com sucesso.
        content:
          application/json:
            schema:
              # Schema para resultado JSON SPARQL padrão (get_sparq_obj)
              type: object
              properties:
                head:
                  type: object
                  properties:
                    vars:
                      type: array
                      items:
                        type: string
                      example: ["obj", "titulo", "resumo", "descricao", "colecao", "tipos"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object # Exemplo de um binding
                        properties:
                          obj: {"type": "object", "properties": {"type": {"type": "string", "example": "uri"}, "value": {"type": "string", "format": "uri", "example": "http://example.org/obj/Mesa123"}}}
                          titulo: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Mesa de Jantar Antiga"}}}
                          # Adicionar outras vars conforme a query get_sparq_obj
      400:
        description: Requisição inválida (ex parâmetros obrigatórios ausentes).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'repository_sparql_endpoint' é obrigatório."}
      500:
        description: Erro interno no servidor ou falha na comunicação SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "RequestException"}
                message: {"type": "string", "example": "Connection refused"}
    """
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid input", "message": "Request body cannot be empty for POST"}), 400
    elif request.method == 'GET':
        data = request.args
    else:
        return jsonify({"error": "Method Not Allowed"}), 405

    keyword = data.get('keyword')
    repo_sparql_endpoint = data.get('repository_sparql_endpoint') 

    if not keyword: 
        return jsonify({"error": "Invalid input", "message": "Campo 'keyword' é obrigatório."}), 400
    if not repo_sparql_endpoint:
        return jsonify({"error": 'Invalid input', "message": "Campo 'repository_sparql_endpoint' é obrigatório."}), 400
    
    repo_base_uri_inferred = repo_sparql_endpoint.rsplit('/', 1)[0] + "#"

    try:
        sparql_query = f'PREFIX : <{repo_base_uri_inferred}> ' + get_sparq_obj().replace('%keyword%', keyword)
        
        current_app.logger.debug(f"Querying {repo_sparql_endpoint} with SPARQL: {sparql_query}")
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        payload_data = {'query': sparql_query}
        encoded_payload = urlencode(payload_data)
        
        response = requests.post(repo_sparql_endpoint, headers=headers, data=encoded_payload, timeout=10)
        response.raise_for_status() 
        
        result = response.json()
        return jsonify(result)

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL query failed for {repo_sparql_endpoint}: {http_err} - Response: {response.text}")
        return jsonify({"error": f"SPARQL query failed with status {response.status_code}", "message": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for {repo_sparql_endpoint}: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in list_physical_objects: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500

@objectapi_app.route('/listar_arquivos', methods=['GET'])
def list_files_for_physical_object(): 
    """
    Lista arquivos de mídia locais associados a um objeto físico e suas URIs
    correspondentes registradas em um repositório SPARQL via schema:associatedMedia.
    Similar ao endpoint em midiaapi, mas focado em objetos físicos.
    ---
    tags:
      - Objetos Físicos
      - Mídia
    parameters:
      - name: objetoId
        in: query
        type: string
        required: true
        description: ID do objeto físico para o qual as mídias serão listadas.
        example: "objfisico-789-uuid-012"
      - name: repositorio_sparql_endpoint
        in: query
        type: string
        format: uri
        required: true
        description: URL completa do endpoint SPARQL para consulta das mídias associadas.
        example: "http://localhost:3030/meu_dataset/sparql"
      - name: repositorio_base_uri
        in: query
        type: string
        format: uri
        required: true
        description: URI base do repositório (ex http://meudominio.com/objetos#) usada para montar a URI do objeto na consulta SPARQL.
        example: "http://localhost:3030/meu_dataset#"
    responses:
      200:
        description: Lista de mídias e informações retornada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                objeto_id_consultado: {"type": "string", "example": "objfisico-789-uuid-012"}
                path_pasta_uploads: {"type": "string", "example": "/var/www/imagens/objfisico-789-uuid-012"}
                arquivos_locais: { "type": "array", "items": {"type": "string"}, "example": ["componenteA.jpg", "manual.pdf"]}
                midias_associadas_sparql: { "type": "array", "items": { "$ref": "#/components/schemas/MediaSparqlInfo" } } # Referência mantida
                arquivos_combinados: { "type": "array", "items": { "$ref": "#/components/schemas/ArquivoCombinadoInfo" } } # Referência mantida
      400:
        description: Parâmetros de consulta inválidos ou ausentes.
      404:
        description: Pasta de uploads do objeto não encontrada.
      500:
        description: Erro interno no servidor ou falha na configuração/SPARQL.
    # A SECÇÃO components: schemas: FOI REMOVIDA DAQUI E MOVIDA PARA APP.PY
    """
    try:
        objeto_id = request.args.get('objetoId')
        repo_sparql_endpoint = request.args.get('repositorio_sparql_endpoint')
        repo_base_uri = request.args.get('repositorio_base_uri')

        if not objeto_id: return jsonify({"error": "Invalid input", "message": "Parâmetro 'objetoId' é obrigatório."}), 400
        if not repo_sparql_endpoint: return jsonify({"error": "Invalid input", "message": "Parâmetro 'repositorio_sparql_endpoint' é obrigatório."}), 400
        if not repo_base_uri: return jsonify({"error": "Invalid input", "message": "Parâmetro 'repositorio_base_uri' é obrigatório."}), 400

        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"
        
        objeto_uri_completa = f"<{repo_base_uri}{objeto_id}>"

        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            current_app.logger.error("UPLOAD_FOLDER não está configurado.")
            return jsonify({"error": "Server Configuration Error", "message": "UPLOAD_FOLDER não configurado."}), 500
            
        objeto_folder_path = os.path.join(upload_folder, str(objeto_id))
        
        arquivos_locais_lista = []
        if os.path.exists(objeto_folder_path) and os.path.isdir(objeto_folder_path):
            arquivos_locais_lista = os.listdir(objeto_folder_path)

        sparql_query = f"""
            PREFIX schema: <http://schema.org/>
            SELECT ?objeto_associado_uri ?media_uri
            WHERE {{ 
                {objeto_uri_completa} schema:associatedMedia ?media_uri .
                BIND({objeto_uri_completa} AS ?objeto_associado_uri)
            }}
        """
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/sparql-results+json,*/*;q=0.9', 'X-Requested-With': 'XMLHttpRequest'}
        payload_data = {'query': sparql_query}
        encoded_payload = urlencode(payload_data)

        midias_sparql_lista = []
        sparql_response_text = "N/A"
        sparql_response_status = "N/A"

        try:
            response = requests.post(repo_sparql_endpoint, headers=headers, data=encoded_payload, timeout=10)
            sparql_response_status = response.status_code
            sparql_response_text = response.text
            response.raise_for_status()
            sparql_result_json = response.json()
            for item in sparql_result_json.get("results", {}).get("bindings", []):
                midias_sparql_lista.append({
                    "media_uri": item.get("media_uri", {}).get("value"),
                    "objeto_associado_uri": item.get("objeto_associado_uri", {}).get("value")
                })
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Erro na consulta SPARQL em list_files_for_physical_object: {str(e)}")

        arquivos_combinados_map = {
            nome: {"nome_arquivo_local": nome, "uri_sparql_correspondente": None, "presente_localmente": True, "presente_sparql": False}
            for nome in arquivos_locais_lista
        }
        for midia_s in midias_sparql_lista:
            uri_s = midia_s["media_uri"]
            if not uri_s: continue
            nome_da_uri = uri_s.split("/")[-1]
            if nome_da_uri in arquivos_combinados_map:
                arquivos_combinados_map[nome_da_uri]["uri_sparql_correspondente"] = uri_s
                arquivos_combinados_map[nome_da_uri]["presente_sparql"] = True
            else:
                arquivos_combinados_map[uri_s] = {"nome_arquivo_local": nome_da_uri, "uri_sparql_correspondente": uri_s, "presente_localmente": False, "presente_sparql": True}
        
        return jsonify({
            "objeto_id_consultado": objeto_id,
            "path_pasta_uploads": objeto_folder_path if os.path.exists(objeto_folder_path) else "Pasta de uploads não encontrada.",
            "arquivos_locais": arquivos_locais_lista,
            "midias_associadas_sparql": midias_sparql_lista,
            "arquivos_combinados": list(arquivos_combinados_map.values())
        })

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na consulta SPARQL (listar_arquivos obj físico): {http_err}")
        return jsonify({"error": "SPARQL Query HTTP Error", "message": str(http_err), "details": sparql_response_text}), sparql_response_status
    except requests.exceptions.RequestException as req_err:
        current_app.logger.error(f"Erro de Requisição (listar_arquivos obj físico): {req_err}")
        return jsonify({"error": "RequestException", "message": f"Falha na comunicação com o endpoint SPARQL: {str(req_err)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em list_files_for_physical_object: {str(e)}")
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@objectapi_app.route('/create', methods=['POST'])
@token_required
def create_physical_object(): 
    """
    Cria um novo objeto físico no repositório SPARQL.
    ---
    tags:
      - Objetos Físicos
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - titulo
              - resumo 
              - colecao_id 
              - repository_update_url
              - repository_base_uri
            properties:
              descricao:
                type: string
                nullable: true
                description: Descrição detalhada do objeto físico.
                example: "Cadeira de madeira entalhada, século XIX."
              titulo:
                type: string
                description: Título ou nome principal do objeto físico.
                example: "Cadeira Histórica"
              resumo:
                type: string
                description: Resumo ou breve descrição do objeto físico (mapeado para dc:abstract).
                example: "Peça de mobiliário com valor histórico."
              colecao_id:
                type: string
                description: ID local da coleção à qual este objeto físico pertence. A URI da coleção será montada com a repository_base_uri.
                example: "colecao_arqueologia"
              temRelacao: 
                type: array
                items:
                  type: string
                  format: uri
                nullable: true
                description: "Lista de URIs de outros recursos relacionados a este objeto."
                example: ["http://example.org/obj/DocumentoRelacionado1"]
              associatedMedia: 
                type: array
                items:
                  type: string
                  format: uri
                nullable: true
                description: "Lista de URIs de mídias associadas a este objeto."
                example: ["http://example.org/media/foto_cadeira.jpg"]
              tipoFisicoAbreviado: 
                type: array
                items:
                  type: string
                nullable: true
                description: "Lista de nomes locais dos tipos físicos (ex 'Movel', 'Ferramenta'). As URIs serão montadas com a repository_base_uri."
                example: ["Movel", "ArtefatoHistorico"]
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização.
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base para os novos objetos e para referenciar tipos/coleções locais.
                example: "http://localhost:3030/mydataset#"
    responses:
      201:
        description: Objeto físico criado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto físico adicionado com sucesso"}
                id: {"type": "string", "format": "uuid", "example": "123e4567-e89b-12d3-a456-426614174000"}
                object_uri: {"type": "string", "format": "uri", "example": "http://localhost:3030/mydataset#123e4567..."}
      400:
        description: Dados de entrada inválidos.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['titulo', 'resumo', 'colecao_id', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400
    
    if not data['titulo'].strip():
        return jsonify({"error": "Invalid input", "message": "Campo 'titulo' não pode ser vazio."}), 400

    sparql_update_url = data['repository_update_url']
    repo_base_uri = data['repository_base_uri']
    if not repo_base_uri.endswith(('#', '/')):
        repo_base_uri += "#"

    object_id_uuid = str(uuid.uuid4())
    objeto_uri_completa = f"<{repo_base_uri}{object_id_uuid}>"
    colecao_uri_completa = f"<{repo_base_uri}{data['colecao_id']}>" 

    triples = [
        f"{objeto_uri_completa} rdf:type obj:ObjetoFisico",
        f"{objeto_uri_completa} dc:title \"\"\"{data['titulo'].replace('"""', '\\"""')}\"\"\"",
        f"{objeto_uri_completa} dc:abstract \"\"\"{data['resumo'].replace('"""', '\\"""')}\"\"\"", 
        f"{objeto_uri_completa} obj:colecao {colecao_uri_completa}"
    ]
    if data.get('descricao'):
        triples.append(f"{objeto_uri_completa} dc:description \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\"")
    
    if data.get('temRelacao'):
        for rel_uri in data['temRelacao']:
            triples.append(f"{objeto_uri_completa} obj:temRelacao <{rel_uri}>") 
            
    if data.get('associatedMedia'):
        for media_uri in data['associatedMedia']:
            triples.append(f"{objeto_uri_completa} schema:associatedMedia <{media_uri}>")
            
    if data.get('tipoFisicoAbreviado'):
        for tipo_local in data['tipoFisicoAbreviado']:
            tipo_uri_completa = f"<{repo_base_uri}{tipo_local.replace(' ', '_')}>" 
            triples.append(f"{objeto_uri_completa} obj:tipoFisico {tipo_uri_completa}")

    sparql_query = f"""{get_prefix()}
        INSERT DATA {{
            { ' .\n'.join(triples) } .
        }}
    """
    current_app.logger.debug(f"SPARQL Create Object Query: {sparql_query}")

    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        return jsonify({
            "message": "Objeto físico adicionado com sucesso", 
            "id": object_id_uuid,
            "object_uri": objeto_uri_completa.strip("<>")
        }), 201
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for create_physical_object: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for create_physical_object: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in create_physical_object: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@objectapi_app.route('/delete', methods=['DELETE']) 
@token_required
def delete_physical_object(): 
    """
    Exclui um objeto físico do repositório SPARQL usando sua URI completa.
    ---
    tags:
      - Objetos Físicos
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - object_uri_to_delete
              - repository_update_url
            properties:
              object_uri_to_delete:
                type: string
                format: uri
                description: "URI completa do objeto físico a ser excluído."
                example: "http://localhost:3030/mydataset#objfisico-789-uuid-012"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Objeto físico excluído com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto físico excluído com sucesso"}
                object_uri: {"type": "string", "format": "uri", "example": "http://localhost:3030/mydataset#objfisico-789-uuid-012"}
      400:
        description: Dados de entrada inválidos (ex URI ausente).
      404:
        description: Objeto físico não encontrado para exclusão (se a verificação for implementada).
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    object_uri = data.get('object_uri_to_delete')
    sparql_update_url = data.get('repository_update_url')

    if not object_uri or not sparql_update_url:
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_delete' e 'repository_update_url' são obrigatórios."}), 400
    
    obj_uri_sparql = f"<{object_uri}>"

    sparql_query = f"""{get_prefix()}
        DELETE WHERE {{
            {{ {obj_uri_sparql} ?p ?o . }}
            UNION
            {{ ?s ?p_inv {obj_uri_sparql} . }}
        }}
    """
    current_app.logger.debug(f"SPARQL Delete Object Query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status() 
        return jsonify({"message": "Objeto físico excluído com sucesso (ou não existia/nenhuma tripla afetada)", "object_uri": object_uri}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for delete_physical_object: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for delete_physical_object: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in delete_physical_object: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@objectapi_app.route('/remover_relacao', methods=['DELETE']) 
@token_required
def remove_relation_from_physical_object(): 
    """
    Remove uma relação RDF específica (tripla s-p-o) de um objeto físico.
    ---
    tags:
      - Objetos Físicos
      - Relações
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - s 
              - p 
              - o 
              - repository_update_url
            properties:
              s:
                type: string
                description: "URI completa do sujeito da tripla (ex <http://example.org/obj/Mesa123>)."
                example: "<http://localhost:3030/mydataset#objfisico-uuid1>"
              p:
                type: string
                description: "URI completa do predicado da tripla (ex <http://schema.org/material>)."
                example: "<http://schema.org/material>"
              o:
                type: string
                description: "URI completa ou Literal RDF do objeto da tripla (ex <http://dbpedia.org/resource/Wood> ou 'Madeira')."
                example: "'Madeira'"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Relação removida com sucesso (ou não existia).
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relação excluída com sucesso"}
                triple: {"type": "string", "example": "<subj> <pred> <obj> ."}
      400:
        description: Dados de entrada inválidos.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    s_uri = data.get('s')
    p_uri = data.get('p')
    o_val = data.get('o') 
    sparql_update_url = data.get('repository_update_url')

    if not all([s_uri, p_uri, o_val, sparql_update_url]):
        return jsonify({"error": "Invalid input", "message": "Campos 's', 'p', 'o', e 'repository_update_url' são obrigatórios."}), 400

    sparql_query = f"""{get_prefix()}
        DELETE DATA {{
            {s_uri} {p_uri} {o_val} .
        }}
    """
    current_app.logger.debug(f"SPARQL Remove Relation Query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        return jsonify({"message": "Relação excluída com sucesso", "triple": f"{s_uri} {p_uri} {o_val} ."}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for remove_relation: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for remove_relation: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in remove_relation: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@objectapi_app.route('/update', methods=['PUT','POST']) 
@token_required
def update_physical_object(): 
    """
    Atualiza um objeto físico existente no repositório SPARQL.
    ---
    tags:
      - Objetos Físicos
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - object_uri_to_update 
              - titulo
              - resumo 
              - repository_update_url
            properties:
              object_uri_to_update:
                type: string
                format: uri
                description: "URI completa do objeto físico a ser atualizado."
                example: "http://localhost:3030/mydataset#objfisico-uuid1"
              titulo:
                type: string
                description: "Novo título para o objeto físico."
                example: "Cadeira Histórica Restaurada"
              resumo:
                type: string
                description: "Novo resumo (dc:abstract) para o objeto físico."
                example: "Peça de mobiliário do século XIX, restaurada em 2023."
              descricao:
                type: string
                nullable: true
                description: "Nova descrição detalhada (opcional, substitui a antiga se fornecida, remove se vazia/null)."
              colecao_id: 
                type: string
                nullable: true
                description: "ID local da nova coleção. Se fornecido, remove a antiga e adiciona esta."
                example: "colecao_restaurados"
              tipoFisicoAbreviado: 
                type: array
                items:
                  type: string
                nullable: true
                description: "Lista de nomes locais dos novos tipos físicos. Substitui completamente os tipos antigos."
                example: ["MovelRestaurado"]
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri: 
                type: string
                format: uri
                nullable: true 
                description: "URI base para montar URIs de coleção e tipos físicos, se IDs locais forem fornecidos."
                example: "http://localhost:3030/mydataset#"
    responses:
      200:
        description: Objeto físico atualizado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto físico atualizado com sucesso"}
                object_uri: {"type": "string", "format": "uri"}
      400:
        description: Dados de entrada inválidos.
      404:
        description: Objeto físico não encontrado para atualização.
      500:
        description: Erro interno no servidor.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    obj_uri_param = data.get('object_uri_to_update')
    sparql_update_url = data.get('repository_update_url')
    
    if not all([obj_uri_param, sparql_update_url, data.get('titulo'), data.get('resumo')]):
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_update', 'repository_update_url', 'titulo' e 'resumo' são obrigatórios."}), 400

    obj_uri_sparql = f"<{obj_uri_param}>"
    
    delete_clauses = [ 
        f"{obj_uri_sparql} dc:title ?oldTitle .",
        f"{obj_uri_sparql} dc:abstract ?oldAbstract ."
    ]
    insert_clauses = [
        f"{obj_uri_sparql} dc:title \"\"\"{data['titulo'].replace('"""', '\\"""')}\"\"\"",
        f"{obj_uri_sparql} dc:abstract \"\"\"{data['resumo'].replace('"""', '\\"""')}\"\"\""
    ]
    where_optional_clauses = [
        f"OPTIONAL {{ {obj_uri_sparql} dc:title ?oldTitle . }}",
        f"OPTIONAL {{ {obj_uri_sparql} dc:abstract ?oldAbstract . }}"
    ]

    if 'descricao' in data:
        delete_clauses.append(f"{obj_uri_sparql} dc:description ?oldDescription .")
        where_optional_clauses.append(f"OPTIONAL {{ {obj_uri_sparql} dc:description ?oldDescription . }}")
        if data['descricao'] is not None and data['descricao'].strip() != "": 
            insert_clauses.append(f"{obj_uri_sparql} dc:description \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\"")
    
    repo_base_uri = data.get('repository_base_uri')
    if ('colecao_id' in data and data['colecao_id'] is not None) or \
       ('tipoFisicoAbreviado' in data and data['tipoFisicoAbreviado'] is not None):
        if not repo_base_uri:
            return jsonify({"error": "Invalid input", "message": "'repository_base_uri' é obrigatório ao atualizar 'colecao_id' ou 'tipoFisicoAbreviado'."}), 400
        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"

    if 'colecao_id' in data and data['colecao_id'] is not None:
        delete_clauses.append(f"{obj_uri_sparql} obj:colecao ?oldColecao .")
        where_optional_clauses.append(f"OPTIONAL {{ {obj_uri_sparql} obj:colecao ?oldColecao . }}")
        if data['colecao_id'].strip() != "":
            nova_colecao_uri = f"<{repo_base_uri}{data['colecao_id']}>"
            insert_clauses.append(f"{obj_uri_sparql} obj:colecao {nova_colecao_uri}")

    if 'tipoFisicoAbreviado' in data and data['tipoFisicoAbreviado'] is not None: 
        delete_clauses.append(f"{obj_uri_sparql} obj:tipoFisico ?oldTipoFisico .") 
        where_optional_clauses.append(f"OPTIONAL {{ {obj_uri_sparql} obj:tipoFisico ?oldTipoFisico . }}")
        if isinstance(data['tipoFisicoAbreviado'], list):
            for tipo_local in data['tipoFisicoAbreviado']:
                if tipo_local and tipo_local.strip() != "":
                    novo_tipo_uri = f"<{repo_base_uri}{tipo_local.replace(' ', '_')}>"
                    insert_clauses.append(f"{obj_uri_sparql} obj:tipoFisico {novo_tipo_uri}")
    
    delete_block = "\n".join(delete_clauses)
    insert_block = " ;\n".join(insert_clauses) 
    where_block = "\n".join(where_optional_clauses)

    sparql_query = f"""{get_prefix()}
        DELETE {{
            {delete_block}
        }}
        INSERT {{
            {insert_block} .
        }}
        WHERE {{
            {obj_uri_sparql} rdf:type obj:ObjetoFisico . 
            {where_block}
        }}
    """
    current_app.logger.debug(f"SPARQL Update Object Query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        return jsonify({"message": "Objeto físico atualizado com sucesso", "object_uri": obj_uri_param}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for update_physical_object: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for update_physical_object: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in update_physical_object: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500

def _internal_add_relation(sujeito_uri_completa, predicado_uri_completa, objeto_uri_ou_literal, sparql_update_url):
    """Função interna para adicionar uma relação. Assume URIs/literais já formatados."""
    sparql_query = f"""{get_prefix()}
        INSERT DATA {{
            {sujeito_uri_completa} {predicado_uri_completa} {objeto_uri_ou_literal} .
        }}
    """
    current_app.logger.debug(f"Internal Add Relation SPARQL: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)
    
    response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
    response.raise_for_status() 
    return response 

@objectapi_app.route('/adicionar_relacao', methods=['POST'])
@token_required 
def add_relation_to_physical_object(): 
    """
    Adiciona uma relação RDF (tripla s-p-o) onde o sujeito é um objeto físico.
    ---
    tags:
      - Objetos Físicos
      - Relações
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - sujeito_uri 
              - predicado_uri 
              - objeto_uri_ou_literal 
              - repository_update_url
            properties:
              sujeito_uri:
                type: string
                format: uri
                description: "URI completa do objeto físico que é o sujeito da relação."
                example: "<http://localhost:3030/mydataset#objfisico-uuid1>"
              predicado_uri:
                type: string
                format: uri
                description: "URI completa da propriedade (predicado)."
                example: "<http://schema.org/isPartOf>"
              objeto_uri_ou_literal:
                type: string
                description: "URI completa do recurso objeto OU um Literal RDF (ex 'Texto', '123'^^xsd:integer)."
                example: "<http://localhost:3030/mydataset#colecao-uuidA>"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      201:
        description: Relação adicionada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relação adicionada com sucesso"}
                triple: {"type": "string", "example": "<subj> <pred> <obj> ."}
      400:
        description: Dados de entrada inválidos.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    s_uri = data.get('sujeito_uri')
    p_uri = data.get('predicado_uri')
    o_val = data.get('objeto_uri_ou_literal')
    sparql_update_url = data.get('repository_update_url')

    if not all([s_uri, p_uri, o_val, sparql_update_url]):
        return jsonify({"error": "Invalid input", "message": "Campos 'sujeito_uri', 'predicado_uri', 'objeto_uri_ou_literal', e 'repository_update_url' são obrigatórios."}), 400

    try:
        _internal_add_relation(s_uri, p_uri, o_val, sparql_update_url)
        return jsonify({"message": "Relação adicionada com sucesso", "triple": f"{s_uri} {p_uri} {o_val} ."}), 201
    except requests.exceptions.HTTPError as http_err:
        response_obj = http_err.response
        current_app.logger.error(f"SPARQL update failed for add_relation_to_physical_object: {http_err} - Response: {response_obj.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response_obj.text, "status_code": response_obj.status_code}), response_obj.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for add_relation_to_physical_object: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in add_relation_to_physical_object: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500