from flask import Blueprint, request, jsonify, current_app
import os
import uuid
# Importar as funções refatoradas de utils.py
from utils import execute_sparql_query, execute_sparql_update
from consultas import get_sparq_all, get_sparq_dim, get_prefix
from blueprints.auth import token_required # Importar o decorador de token

dimapi_app = Blueprint('dimapi_app', __name__)

@dimapi_app.route('/list', methods=['GET','POST'])
def list_dimensional_objects(): # Renomeado de 'list' para maior clareza
    """
    Lista objetos dimensionais de um repositório SPARQL com base numa palavra-chave e tipo.
    Este endpoint suporta GET (com query parameters) e POST (com JSON body).
    A documentação abaixo foca no método POST. Para GET, use os mesmos parâmetros como query strings.
    ---
    tags:
      - Objetos Dimensionais
    parameters:
      - name: keyword
        in: query
        required: true
        description: Palavra-chave para filtrar os objetos (usado se o método for GET).
        schema:
          type: string
        example: "Festa"
      - name: repository
        in: query
        required: true
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:3030/mydataset/sparql"
      - name: type
        in: query
        required: true
        description: Tipo de objeto dimensional a ser listado (usado se o método for GET, não usado diretamente na query get_sparq_dim).
        schema:
          type: string
        example: "Evento"
    requestBody:
      description: Parâmetros para busca de objetos dimensionais (usado se o método for POST).
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - keyword
              - repository
              - type # Embora 'type' esteja no corpo, a query get_sparq_dim não parece usá-lo diretamente para filtrar por tipo dimensional específico.
            properties:
              keyword:
                type: string
                description: Palavra-chave para filtrar os objetos.
                example: "Procissão"
              repository:
                type: string
                format: uri
                description: URL do endpoint SPARQL do repositório.
                example: "http://localhost:3030/mydataset/sparql"
              type:
                type: string
                description: Tipo de objeto dimensional (informativo, pois a query get_sparq_dim já filtra por obj:Pessoa, obj:Tempo, etc.).
                example: "Lugar"
    responses:
      200:
        description: Lista de objetos dimensionais encontrada com sucesso.
        content:
          application/json:
            schema:
              # Schema para resultado JSON SPARQL padrão
              type: object
              properties:
                head:
                  type: object
                  properties:
                    vars:
                      type: array
                      items:
                        type: string
                      example: ["obj", "titulo", "resumo", "descricao", "dimensao", "lat", "lon"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object # Exemplo de um binding
                        properties:
                          obj:
                            type: object
                            properties:
                              type: {"type": "string", "example": "uri"}
                              value: {"type": "string", "format": "uri", "example": "http://example.org/obj/Evento1"}
                          titulo:
                            type: object
                            properties:
                              type: {"type": "string", "example": "literal"}
                              value: {"type": "string", "example": "Festa de Aniversário"}
                          # Adicionar outras vars conforme a query get_sparq_dim
      400:
        description: Requisição inválida (ex parâmetros obrigatórios ausentes).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'repository' é obrigatório."}
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
    repo = data.get('repository')
    # obj_type = data.get('type') # 'type' não é usado na query get_sparq_dim, ela já tem os tipos fixos.

    if not keyword:
        return jsonify({"error": "Invalid input", "message": "Campo 'keyword' é obrigatório."}), 400
    if not repo:
        return jsonify({"error": 'Invalid input', "message": "Campo 'repository' é obrigatório."}), 400

    sparqapi_url = repo # URL do repositório é o endpoint SPARQL

    try:
        # A query get_sparq_dim já filtra por obj:Pessoa, obj:Tempo, obj:Lugar, obj:Evento
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_dim().replace('%keyword%', keyword)

        # Usando execute_sparql_query de utils.py
        result = execute_sparql_query(sparqapi_url, sparql_query)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Erro ao listar objetos dimensionais: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_query
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Query Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

@dimapi_app.route('/listall', methods=['GET','POST'])
def list_all_dimensional_or_physical(): # Renomeado de 'list_all'
    """
    Lista todos os objetos (físicos ou dimensionais) de um tipo específico ou todos se nenhum tipo for especificado,
    filtrados por palavra-chave.
    Este endpoint suporta GET (com query parameters) e POST (com JSON body).
    A documentação abaixo foca no método POST. Para GET, use os mesmos parâmetros como query strings.
    ---
    tags:
      - Objetos Dimensionais
      - Objetos Físicos
    parameters:
      - name: repository
        in: query
        required: true
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:3030/mydataset/sparql"
      - name: type
        in: query
        required: false
        description: Tipo de objeto para listar (quem, quando, onde, oque, fisico). Se omitido, busca em todos os tipos. (usado se o método for GET).
        schema:
          type: string
          enum: ["quem", "quando", "onde", "oque", "fisico"]
        example: "quem"
      - name: keyword
        in: query
        required: false # A query original get_sparq_all() usa %keyword%
        description: Palavra-chave para filtrar os resultados (usado se o método for GET).
        schema:
          type: string
        example: "José"
    requestBody:
      description: Parâmetros para listar objetos (usado se o método for POST).
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - repository
            properties:
              repository:
                type: string
                format: uri
                description: URL do endpoint SPARQL do repositório.
                example: "http://localhost:3030/mydataset/sparql"
              type:
                type: string
                required: false
                description: Tipo de objeto para listar (quem, quando, onde, oque, fisico). Se omitido, busca em todos os tipos.
                enum: ["quem", "quando", "onde", "oque", "fisico"]
                example: "fisico"
              keyword:
                type: string
                required: false # Assumindo que pode ser opcional
                description: Palavra-chave para filtrar os resultados.
                example: "documento"
    responses:
      200:
        description: Lista de objetos encontrada com sucesso.
        content:
          application/json:
            schema:
              # Schema para resultado JSON SPARQL padrão (get_sparq_all)
              type: object
              properties:
                head:
                  type: object
                  properties:
                    vars:
                      type: array
                      items:
                        type: string
                      example: ["id", "titulo", "descricao", "assunto", "tipo", "dimensao", "tipoFisico"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object # Exemplo de um binding
                        properties:
                          id: {"type": "object", "properties": {"type": {"type": "string", "example": "uri"}, "value": {"type": "string", "format": "uri", "example": "http://example.org/obj/Doc1"}}}
                          titulo: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Relatório Anual"}}}
                          # Adicionar outras vars conforme a query get_sparq_all
      400:
        description: Requisição inválida.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'repository' é obrigatório."}
      500:
        description: Erro interno no servidor.
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

    repo = data.get('repository')
    tipo_param = data.get('type', '') # Default para string vazia se não fornecido
    keyword = data.get('keyword', '')   # Default para string vazia se não fornecido

    if not repo:
        return jsonify({"error": 'Invalid input', "message": "Campo 'repository' é obrigatório."}), 400

    sparqapi_url = repo

    # Mapeamento do parâmetro 'type' para o filtro SPARQL
    # Se tipo_param for vazio, replace_tipo também será, e a query original get_sparq_all não filtrará por um tipo específico.
    replace_tipo = {
        'quem': 'a obj:Pessoa;',
        'quando': 'a obj:Tempo;',
        'onde': 'a obj:Lugar;',
        'oque': 'a obj:Evento;',
        'fisico': 'a obj:ObjetoFisico;'
    }.get(tipo_param.lower(), '') # .lower() para case-insensitivity do parâmetro

    try:
        sparql_query = f'PREFIX : <{repo}#> ' + get_sparq_all()
        sparql_query = sparql_query.replace('%keyword%', keyword)
        sparql_query = sparql_query.replace('%tipo%', replace_tipo) # %tipo% será substituído por vazio se tipo_param não corresponder

        # Usando execute_sparql_query de utils.py
        result = execute_sparql_query(sparqapi_url, sparql_query)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Erro ao listar todos os objetos: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_query
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Query Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@dimapi_app.route('/listar_arquivos', methods=['GET'])
def listar_arquivos_objeto_dimensional(): # Renomeado de 'listar_arquivos'
    """
    Lista arquivos locais e arquivos associados via SPARQL para um objeto específico.
    ---
    tags:
      - Objetos Dimensionais
      - Mídia
    parameters:
      - name: objetoId
        in: query
        type: string
        required: true
        description: ID do objeto para listar os arquivos.
        example: "123e4567-e89b-12d3-a456-426614174000"
      - name: repositorio
        in: query
        type: string
        format: uri
        required: true
        description: URL do endpoint SPARQL do repositório para consulta.
        example: "http://localhost:3030/mydataset/sparql"
    responses:
      200:
        description: Lista de arquivos locais e URIs SPARQL associados.
        content:
          application/json:
            schema:
              type: object
              properties:
                arquivos_locais:
                  type: array
                  items:
                    type: string
                  description: Lista de nomes de arquivos encontrados localmente na pasta do objeto.
                  example: ["imagem1.jpg", "documento.pdf"]
                arquivos_sparql: # Resultado bruto da query SPARQL por schema:associatedMedia
                  type: object
                  description: Resultado da consulta SPARQL por mídias associadas.
                arquivos_combinados:
                  type: array
                  items:
                    type: object
                    properties:
                      nome:
                        type: string
                        description: Nome do arquivo.
                        example: "imagem1.jpg"
                      uri:
                        type: string
                        format: uri
                        nullable: true # Pode não ter URI no grafo se for apenas local
                        description: URI associada ao arquivo via schema:associatedMedia no SPARQL.
                        example: "http://example.org/media/imagem1.jpg"
                  description: Lista combinada de arquivos locais com suas URIs SPARQL, se existentes.
                path_folder:
                  type: string
                  description: Caminho absoluto no servidor para a pasta de uploads do objeto.
                  example: "/var/www/imagens/123e4567-e89b-12d3-a456-426614174000"
      400:
        description: Parâmetros de entrada inválidos (ex objetoId ou repositorio ausente).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Parâmetro 'objetoId' é obrigatório."}
      500:
        description: Erro interno do servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Exception"}
                message: {"type": "string", "example": "Erro ao processar a listagem de arquivos."}
    """
    try:
        objeto_id = request.args.get('objetoId')
        repo_sparql_url = request.args.get('repositorio') # URL do endpoint SPARQL

        if not objeto_id:
            return jsonify({"error": "Invalid input", "message": "Parâmetro 'objetoId' é obrigatório."}), 400
        if not repo_sparql_url:
            return jsonify({"error": "Invalid input", "message": "Parâmetro 'repositorio' (URL do endpoint SPARQL) é obrigatório."}), 400


        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            return jsonify({"error": "Server Configuration Error", "message": "UPLOAD_FOLDER não configurado."}), 500

        objeto_folder_path = os.path.join(upload_folder, str(objeto_id))

        arquivos_locais_lista = []
        if os.path.exists(objeto_folder_path) and os.path.isdir(objeto_folder_path):
            arquivos_locais_lista = os.listdir(objeto_folder_path)

        # A query SPARQL precisa da URI base do repositório para construir :objeto_id
        # Vamos assumir que repo_sparql_url é o endpoint de query, e precisamos inferir a base_uri
        # Esta é uma simplificação; idealmente, a base_uri seria configurada ou passada.
        # Exemplo: http://localhost:3030/mydataset/sparql -> http://localhost:3030/mydataset#
        repo_base_uri_inferred = repo_sparql_url.rsplit('/', 1)[0] + "#"


        sparql_query = f"""
            PREFIX schema: <http://schema.org/>
            PREFIX : <{repo_base_uri_inferred}>
            SELECT ?s ?media_uri
            WHERE {{
                :{objeto_id} schema:associatedMedia ?media_uri .
                BIND(:{objeto_id} AS ?s) # Para manter a estrutura da resposta original que tinha ?a
            }}
        """

        sparql_result_json = {}
        try:
            # Usando execute_sparql_query de utils.py
            sparql_result_json = execute_sparql_query(repo_sparql_url, sparql_query)
        except Exception as e:
            current_app.logger.warning(f"Aviso: Consulta SPARQL para mídias associadas falhou: {str(e)}")
            # Não retornar erro fatal aqui, pode haver arquivos locais mesmo sem SPARQL

        arquivos_map = {nome: {"nome": nome, "uri": None} for nome in arquivos_locais_lista}

        for item in sparql_result_json.get("results", {}).get("bindings", []):
            media_uri_value = item.get("media_uri", {}).get("value")
            if media_uri_value:
                # Tenta extrair o nome do arquivo da URI para correspondência
                # Isso é uma heurística e pode precisar de ajuste dependendo da estrutura da URI da mídia
                nome_arquivo_da_uri = media_uri_value.split("/")[-1]

                if nome_arquivo_da_uri in arquivos_map:
                    arquivos_map[nome_arquivo_da_uri]["uri"] = media_uri_value
                else: # Mídia existe no SPARQL mas não localmente (ou nome não bate)
                    arquivos_map[nome_arquivo_da_uri] = {"nome": nome_arquivo_da_uri, "uri": media_uri_value}

        arquivos_combinados_lista = list(arquivos_map.values())

        return jsonify({
            "arquivos_locais": arquivos_locais_lista,
            "arquivos_sparql": sparql_result_json, # Retorna o resultado bruto do SPARQL também
            "arquivos_combinados": arquivos_combinados_lista,
            "path_folder": objeto_folder_path,
        })

    except Exception as e:
        current_app.logger.error(f"Erro inesperado em listar_arquivos_objeto_dimensional: {str(e)}")
        # Captura outras exceções não relacionadas ao SPARQL
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

@dimapi_app.route('/create', methods=['POST'])
@token_required # Protegendo o endpoint
def create_dimensional_object(): # Renomeado de 'create'
    """
    Cria um novo objeto dimensional (Pessoa, Lugar, Tempo, Evento) no repositório SPARQL.
    ---
    tags:
      - Objetos Dimensionais
    security:
      - BearerAuth: [] # Referenciar a definição de segurança global
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - titulo
              - resumo
              - tipo_uri # URI completa do tipo dimensional (ex http://guara.ueg.br/ontologias/v1/objetos#Pessoa)
              - repository_update_url
              - repository_base_uri
            properties:
              descricao:
                type: string
                nullable: true
                description: Descrição detalhada do objeto dimensional.
                example: "Participou de eventos históricos importantes na região."
              titulo:
                type: string
                description: Título ou nome principal do objeto dimensional.
                example: "João Silva"
              resumo: # 'abstract' no DC, 'subject' na query original de update. Usando 'resumo' para consistência com outros endpoints.
                type: string
                description: Resumo ou breve descrição do objeto dimensional.
                example: "Historiador e pesquisador local."
              tipo_uri:
                type: string
                format: uri
                description: URI completa do tipo do objeto dimensional (ex obj:Pessoa, obj:Lugar).
                example: "http://guara.ueg.br/ontologias/v1/objetos#Pessoa"
              coordenadas: # Para obj:Lugar
                type: string
                nullable: true
                description: "Coordenadas geográficas no formato 'latitude,longitude'. Aplicável para tipo Lugar."
                example: "-16.3285,-48.9534"
              temRelacao:
                type: array
                items:
                  type: string
                  format: uri
                nullable: true
                description: "Lista de URIs de outros recursos relacionados a este objeto."
                example: ["http://example.org/obj/EventoX", "http://example.org/obj/DocumentoY"]
              associatedMedia:
                type: array
                items:
                  type: string
                  format: uri
                nullable: true
                description: "Lista de URIs de mídias associadas a este objeto."
                example: ["http://example.org/media/foto_joao.jpg"]
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização do repositório.
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri: # Usado para construir a URI do novo objeto
                type: string
                format: uri
                description: URI base para os novos objetos neste repositório.
                example: "http://localhost:3030/mydataset#"
    responses:
      201:
        description: Objeto dimensional criado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Objeto dimensional adicionado com sucesso"
                id: # UUID gerado
                  type: string
                  format: uuid
                  example: "123e4567-e89b-12d3-a456-426614174000"
                object_uri:
                  type: string
                  format: uri
                  example: "http://localhost:3030/mydataset#123e4567-e89b-12d3-a456-426614174000"
      400:
        description: Dados de entrada inválidos (ex campos obrigatórios ausentes).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'titulo' é obrigatório."}
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "SPARQL Update Error"}
                message: {"type": "string", "example": "Detalhes do erro."}
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['titulo', 'resumo', 'tipo_uri', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    sparql_update_url = data['repository_update_url']
    repo_base_uri = data['repository_base_uri']
    if not repo_base_uri.endswith(('#', '/')):
        repo_base_uri += "#"

    object_id = str(uuid.uuid4())
    objeto_uri_completa = f"<{repo_base_uri}{object_id}>"

    tipo_obj_uri = f"<{data['tipo_uri']}>" # URI completa do tipo (ex: <http://...#Pessoa>)

    # Construção das partes da query
    triples = [
        f"{objeto_uri_completa} rdf:type {tipo_obj_uri}",
        f"{objeto_uri_completa} rdf:type obj:ObjetoDimensional", # Superclasse genérica
        f"{objeto_uri_completa} dc:title \"\"\"{data['titulo'].replace('"""', '\\"""')}\"\"\"",
        f"{objeto_uri_completa} dc:abstract \"\"\"{data['resumo'].replace('"""', '\\"""')}\"\"\"" # Usando dc:abstract para resumo
    ]
    if data.get('descricao'):
        triples.append(f"{objeto_uri_completa} dc:description \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\"")

    if data.get('coordenadas'):
        try:
            lat, lon = map(str.strip, data['coordenadas'].split(','))
            triples.append(f"{objeto_uri_completa} geo:lat \"{lat}\"")
            triples.append(f"{objeto_uri_completa} geo:long \"{lon}\"")
        except ValueError:
            return jsonify({"error": "Invalid input", "message": "Formato de 'coordenadas' inválido. Use 'latitude,longitude'."}), 400

    if data.get('temRelacao'):
        for rel_uri in data['temRelacao']:
            triples.append(f"{objeto_uri_completa} obj:temRelacao <{rel_uri}>") # Usando obj:temRelacao ou similar

    if data.get('associatedMedia'):
        for media_uri in data['associatedMedia']:
            triples.append(f"{objeto_uri_completa} schema:associatedMedia <{media_uri}>")

    sparql_update = f"""{get_prefix()}
        INSERT DATA {{
            { ' .\n'.join(triples) } .
        }}
    """
    current_app.logger.debug(f"SPARQL Create Dimensional Object Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({
            "message": "Objeto dimensional adicionado com sucesso",
            "id": object_id,
            "object_uri": objeto_uri_completa.strip("<>")
        }), 201
    except Exception as e:
        current_app.logger.error(f"Erro ao criar objeto dimensional: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@dimapi_app.route('/delete', methods=['DELETE','POST']) # Manter POST se necessário, DELETE é mais semântico
@token_required
def excluir_dimensional_object(): # Renomeado de 'excluir'
    """
    Exclui um objeto dimensional (ou qualquer objeto por URI) do repositório SPARQL.
    ---
    tags:
      - Objetos Dimensionais
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - object_uri_to_delete # Alterado de 'id' para 'object_uri_to_delete' para clareza
              - repository_update_url
              - repository_base_uri # Para construir a URI completa se apenas o ID local for passado
            properties:
              object_uri_to_delete:
                type: string
                format: uri # Ou apenas o ID local se repository_base_uri for usado para montá-la
                description: "URI completa do objeto a ser excluído OU ID local se repository_base_uri for fornecida."
                example: "http://localhost:3030/mydataset#123e4567-e89b-12d3-a456-426614174000"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri: # Opcional se object_uri_to_delete for sempre completa
                type: string
                format: uri
                nullable: true
                description: "URI base do repositório, usada se 'object_uri_to_delete' for um ID local."
                example: "http://localhost:3030/mydataset#"
    responses:
      200:
        description: Objeto excluído com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto excluído com sucesso"}
                object_uri: {"type": "string", "format": "uri", "example": "http://localhost:3030/mydataset#123e4567... "}
      400:
        description: Dados de entrada inválidos.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'object_uri_to_delete' é obrigatório."}
      404: # Se o objeto não existir para ser deletado
        description: Objeto não encontrado.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Not Found"}
                message: {"type": "string", "example": "Objeto não encontrado para exclusão."}
      500:
        description: Erro interno no servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "SPARQL Update Error"}
                message: {"type": "string"}
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    object_identifier = data.get('object_uri_to_delete') # Pode ser URI completa ou ID local
    sparql_update_url = data.get('repository_update_url')
    repo_base_uri = data.get('repository_base_uri')

    if not object_identifier or not sparql_update_url:
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_delete' e 'repository_update_url' são obrigatórios."}), 400

    # Construir URI completa se necessário
    if "://" in object_identifier: # Heurística para checar se é uma URI completa
        objeto_uri_sparql = f"<{object_identifier}>"
    elif repo_base_uri:
        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"
        objeto_uri_sparql = f"<{repo_base_uri}{object_identifier}>"
    else:
        return jsonify({"error": "Invalid input", "message": "Se 'object_uri_to_delete' for um ID local, 'repository_base_uri' é obrigatório."}), 400

    # Query para deletar todas as triplas onde o objeto é sujeito E onde ele é objeto
    sparql_update = f"""
        DELETE WHERE {{
            {{ {objeto_uri_sparql} ?p ?o . }}
            UNION
            {{ ?s ?p_inv {objeto_uri_sparql} . }}
        }}
    """
    current_app.logger.debug(f"SPARQL Delete Dimensional Object Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({"message": "Objeto excluído com sucesso", "object_uri": objeto_uri_sparql.strip("<>")}), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao excluir objeto dimensional: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

@dimapi_app.route('/remover_relacao', methods=['DELETE','POST']) # Manter POST se necessário
@token_required
def remover_relacao_dimensional(): # Renomeado de 'remover_relacao'
    """
    Remove uma relação RDF específica (tripla s-p-o) de um repositório SPARQL.
    ---
    tags:
      - Objetos Dimensionais
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
              - s # Sujeito da tripla
              - p # Predicado da tripla
              - o # Objeto da tripla
              - repository_update_url
            properties:
              s:
                type: string
                description: "URI completa do sujeito da tripla (ex <http://example.org/s1>)."
                example: "<http://example.org/objeto/RecursoA>"
              p:
                type: string
                description: "URI completa do predicado da tripla (ex <http://purl.org/dc/terms/relation>)."
                example: "<http://schema.org/knows>"
              o:
                type: string
                # Pode ser URI ou Literal. Se literal, deve ser formatado (ex "Texto" ou "10"^^xsd:integer)
                description: "URI completa ou Literal RDF do objeto da tripla (ex <http://example.org/o1> ou 'Literal')."
                example: "<http://example.org/pessoa/PessoaB>"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Relação removida com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relação excluída com sucesso"}
                triple: {"type": "string", "example": "<http://example.org/s1> <http://purl.org/dc/terms/title> Título"}
      400:
        description: Dados de entrada inválidos.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campos 's', 'p', 'o' e 'repository_update_url' são obrigatórios."}
      500:
        description: Erro interno no servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "SPARQL Update Error"}
                message: {"type": "string"}
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    s = data.get('s') # Espera-se URI completa ou literal formatado (ex: <uri> ou "literal"^^xsd:string)
    p = data.get('p') # Espera-se URI completa (ex: <uri>)
    o = data.get('o') # Espera-se URI completa ou literal formatado
    sparql_update_url = data.get('repository_update_url')

    if not all([s, p, o, sparql_update_url]):
        return jsonify({"error": "Invalid input", "message": "Campos 's', 'p', 'o' e 'repository_update_url' são obrigatórios."}), 400

    sparql_update = f"""
        DELETE DATA {{
            {s} {p} {o} .
        }}
    """
    current_app.logger.debug(f"SPARQL Remove Relation Dimensional Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({"message": "Relação excluída com sucesso", "triple": f"{s} {p} {o}"}), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao remover relação dimensional: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

@dimapi_app.route('/update', methods=['PUT', 'POST']) # PUT é mais semântico para update completo
@token_required
def update_dimensional_object(): # Renomeado de 'update'
    """
    Atualiza os metadados de um objeto dimensional existente.
    ---
    tags:
      - Objetos Dimensionais
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - object_uri_to_update # URI completa do objeto a ser atualizado
              - titulo
              - resumo
              # tipo_uri não é alterado aqui, mas poderia ser se necessário
              - repository_update_url
            properties:
              object_uri_to_update:
                type: string
                format: uri
                description: "URI completa do objeto dimensional a ser atualizado."
                example: "http://localhost:3030/mydataset#123e4567-e89b-12d3-a456-426614174000"
              titulo:
                type: string
                description: "Novo título para o objeto."
                example: "João Silva (Revisado)"
              resumo:
                type: string
                description: "Novo resumo para o objeto."
                example: "Historiador local, com foco em tradições orais."
              descricao:
                type: string
                nullable: true
                description: "Nova descrição detalhada (opcional)."
                example: "Após novas pesquisas, a descrição foi expandida."
              coordenadas:
                type: string
                nullable: true
                description: "Novas coordenadas 'latitude,longitude' (opcional, aplicável a Lugares)."
                example: "-16.3290,-48.9540"
              # Adicionar temRelacao e associatedMedia se a atualização deles for suportada por este endpoint
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Objeto atualizado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto atualizado com sucesso"}
                object_uri: {"type": "string", "format": "uri", "example": "http://localhost:3030/mydataset#123e4567..."}
      400:
        description: Dados de entrada inválidos.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'object_uri_to_update' é obrigatório."}
      404:
        description: Objeto não encontrado para atualização.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Not Found"}
                message: {"type": "string", "example": "Objeto não encontrado."}
      500:
        description: Erro interno no servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "SPARQL Update Error"}
                message: {"type": "string"}
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    object_uri = data.get('object_uri_to_update')
    sparql_update_url = data.get('repository_update_url')

    if not all([object_uri, sparql_update_url, data.get('titulo'), data.get('resumo')]):
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_update', 'repository_update_url', 'titulo' e 'resumo' são obrigatórios."}), 400

    obj_uri_sparql = f"<{object_uri}>"

    # Construção dos blocos DELETE e INSERT
    delete_clauses = []
    insert_clauses = [
        f"{obj_uri_sparql} dc:title \"\"\"{data['titulo'].replace('"""', '\\"""')}\"\"\"",
        f"{obj_uri_sparql} dc:abstract \"\"\"{data['resumo'].replace('"""', '\\"""')}\"\"\""
    ]
    where_clauses = [f"OPTIONAL {{ {obj_uri_sparql} dc:title ?oldTitle . }}",
                     f"OPTIONAL {{ {obj_uri_sparql} dc:abstract ?oldAbstract . }}"] # dc:abstract para resumo

    # Campos opcionais para atualização
    if 'descricao' in data: # Permite remover descrição se "" for passado, ou atualizar
        delete_clauses.append(f"{obj_uri_sparql} dc:description ?oldDescription .")
        where_clauses.append(f"OPTIONAL {{ {obj_uri_sparql} dc:description ?oldDescription . }}")
        if data['descricao'] is not None and data['descricao'].strip() != "":
             insert_clauses.append(f"{obj_uri_sparql} dc:description \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\"")
        # Se data['descricao'] for "" ou None, a descrição antiga é removida e nenhuma nova é inserida.

    if 'coordenadas' in data:
        delete_clauses.extend([f"{obj_uri_sparql} geo:lat ?oldLat .", f"{obj_uri_sparql} geo:long ?oldLong ."])
        where_clauses.extend([f"OPTIONAL {{ {obj_uri_sparql} geo:lat ?oldLat . }}", f"OPTIONAL {{ {obj_uri_sparql} geo:long ?oldLong . }}"])
        if data['coordenadas'] is not None and data['coordenadas'].strip() != "":
            try:
                lat, lon = map(str.strip, data['coordenadas'].split(','))
                insert_clauses.extend([f"{obj_uri_sparql} geo:lat \"{lat}\"", f"{obj_uri_sparql} geo:long \"{lon}\""])
            except ValueError:
                return jsonify({"error": "Invalid input", "message": "Formato de 'coordenadas' inválido. Use 'latitude,longitude'."}), 400
        # Se data['coordenadas'] for "" ou None, as coordenadas antigas são removidas.

    delete_block = "\n".join(delete_clauses)
    insert_block = " ;\n".join(insert_clauses) # Junta as triplas de insert com ;
    where_block = "\n".join(where_clauses)

    sparql_update = f"""{get_prefix()}
        DELETE {{
            {delete_block}
        }}
        INSERT {{
            {insert_block} .
        }}
        WHERE {{
            {obj_uri_sparql} ?anyProp ?anyVal . # Garante que o objeto existe para aplicar o WHERE nos OPTIONALs
            {where_block}
        }}
    """
    current_app.logger.debug(f"SPARQL Update Dimensional Object Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({"message": "Objeto atualizado com sucesso", "object_uri": object_uri}), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao atualizar objeto dimensional: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@dimapi_app.route('/update_old', methods=['PUT','POST'])
@token_required
def update_dimensional_object_old(): # Renomeado de 'update_old'
    """
    (Versão Antiga/Simplificada) Atualiza descrição, título e resumo de um objeto.
    Considere usar o endpoint /update para uma atualização mais completa.
    ---
    tags:
      - Objetos Dimensionais
      - Deprecated
    deprecated: true # Marcando como deprecated
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - id # ID local do objeto
              - descricao
              - titulo
              - resumo
              - repository_update_url
              - repository_base_uri # Para construir a URI completa do objeto
            properties:
              id:
                type: string
                description: "ID local do objeto a ser atualizado."
                example: "123e4567-e89b-12d3-a456-426614174000"
              descricao:
                type: string
                example: "Descrição atualizada do objeto."
              titulo:
                type: string
                example: "Título Atualizado"
              resumo:
                type: string
                example: "Resumo atualizado."
              repository_update_url:
                type: string
                format: uri
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri:
                type: string
                format: uri
                example: "http://localhost:3030/mydataset#"
              # 'tipo' e 'coordenadas' do request original não são usados na query SPARQL deste endpoint.
    responses:
      200:
        description: Objeto atualizado com sucesso (versão antiga).
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Objeto atualizado com sucesso"}
                id: {"type": "string", "example": "123e4567-e89b-12d3-a456-426614174000"}
      400:
        description: Dados de entrada inválidos.
      404:
        description: Objeto não encontrado.
      500:
        description: Erro interno no servidor.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['id', 'descricao', 'titulo', 'resumo', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    object_id_local = data['id']
    sparql_update_url = data['repository_update_url']
    repo_base_uri = data['repository_base_uri']
    if not repo_base_uri.endswith(('#', '/')):
        repo_base_uri += "#"

    objeto_uri_sparql = f"<{repo_base_uri}{object_id_local}>"

    description_val = data['descricao'].replace('"""', '\\"""')
    abstract_val = data['resumo'].replace('"""', '\\"""') # dc:abstract para resumo
    title_val = data['titulo'].replace('"""', '\\"""')

    sparql_update = f"""{get_prefix()}
        DELETE {{
            {objeto_uri_sparql} dc:description ?oldDescription;
                               dc:title ?oldTitle;
                               dc:abstract ?oldAbstract.
        }}
        INSERT {{
            {objeto_uri_sparql} dc:description \"\"\"{description_val}\"\"\";
                               dc:title \"\"\"{title_val}\"\"\";
                               dc:abstract \"\"\"{abstract_val}\"\"\" .
        }}
        WHERE {{
            {objeto_uri_sparql} ?anyProp ?anyVal . # Garante que o objeto existe
            OPTIONAL {{ {objeto_uri_sparql} dc:description ?oldDescription . }}
            OPTIONAL {{ {objeto_uri_sparql} dc:title ?oldTitle . }}
            OPTIONAL {{ {objeto_uri_sparql} dc:abstract ?oldAbstract . }}
        }}
    """
    current_app.logger.debug(f"SPARQL Update Dimensional Object (Old) Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({"message": "Objeto atualizado com sucesso", "id": object_id_local}), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao atualizar objeto dimensional (antigo): {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

@dimapi_app.route('/add_relation', methods=['POST'])
@token_required
def add_relation_dimensional(): # Renomeado de 'add_relation'
    """
    Adiciona uma relação RDF entre um objeto dimensional (sujeito) e outro recurso (objeto).
    ---
    tags:
      - Objetos Dimensionais
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
              - s # Sujeito URI
              - p # Predicado URI
              - o # Objeto URI ou Literal
              - repository_update_url
            properties:
              s:
                type: string
                format: uri # Espera-se URI completa <...>
                description: "URI completa do objeto sujeito da relação."
                example: "<http://localhost:3030/mydataset#ObjetoA>"
              p:
                type: string
                format: uri # Espera-se URI completa <...>
                description: "URI completa da propriedade (predicado) da relação."
                example: "<http://schema.org/relatedTo>"
              o:
                type: string
                # Pode ser URI ou Literal. Se literal, deve ser formatado (ex "Texto" ou "10"^^xsd:integer)
                description: "URI completa do objeto da relação ou um Literal RDF."
                example: "<http://localhost:3030/mydataset#ObjetoB>"
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
              # 'repositorio_uri' do request original não é usado na query, apenas 'repository_update_url' (que era 'repo')
    responses:
      201: # Mudado para 201 Created, pois uma nova relação é criada
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
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 's' (sujeito) é obrigatório."}
      500:
        description: Erro interno no servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "SPARQL Update Error"}
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    # No request original, os campos eram "o" (para sujeito), "midia_uri" (para objeto), "propriedade", "repositorio_uri", "repository"
    # Mapeando para s, p, o para clareza semântica de triplas RDF
    sujeito = data.get('s') # URI do sujeito
    predicado = data.get('p') # URI da propriedade
    objeto_rdf = data.get('o') # URI ou Literal do objeto
    sparql_update_url = data.get('repository_update_url')

    if not all([sujeito, predicado, objeto_rdf, sparql_update_url]):
        return jsonify({"error": "Invalid input", "message": "Campos 's', 'p', 'o', e 'repository_update_url' são obrigatórios."}), 400

    # Assume que s, p, o já estão formatados corretamente para SPARQL (ex: <uri> ou "literal"^^<datatype>)
    sparql_update = f"""{get_prefix()}
        INSERT DATA {{
            {sujeito} {predicado} {objeto_rdf} .
        }}
    """
    current_app.logger.debug(f"SPARQL Add Relation Dimensional Update: {sparql_update}")

    try:
        # Usando execute_sparql_update de utils.py
        execute_sparql_update(sparql_update_url, sparql_update)
        return jsonify({"message": "Relação adicionada com sucesso", "triple": f"{sujeito} {predicado} {objeto_rdf} ."}), 201
    except Exception as e:
        current_app.logger.error(f"Erro ao adicionar relação dimensional: {str(e)}")
        # Captura as exceções levantadas por execute_sparql_update
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
