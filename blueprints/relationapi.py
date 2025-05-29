from flask import Blueprint, request, jsonify,current_app
import requests, os
import uuid # Não usado diretamente nos endpoints atuais
from consultas import get_prefix # get_sparq_all e get_sparq_dim não são usados aqui
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required # Importar o decorador de token

relationapi_app = Blueprint('relationapi_app', __name__)

@relationapi_app.route('/list', methods=['GET','POST'])
def list_relations_of_object(): # Renomeado de 'list'
    """
    Lista todas as relações (diretas e inversas) de um objeto específico em um repositório RDF.
    Retorna as propriedades, valores, tipo do valor (URI ou Literal) e título do valor (se for URI e tiver dc:title).
    Este endpoint suporta GET (com query parameters) e POST (com JSON body).
    A documentação abaixo foca no método POST. Para GET, use os mesmos parâmetros como query strings.
    ---
    tags:
      - Relações
    parameters:
      - name: id_objeto # Renomeado de 'id'
        in: query
        required: true
        description: URI completa do objeto cujas relações serão listadas (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:3030/mydataset#Objeto123"
      - name: repository_sparql_endpoint # Renomeado de 'repository'
        in: query
        required: true
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:3030/mydataset/sparql"
      # 'keyword' e 'type' do request original não parecem ser usados na query SPARQL deste endpoint.
      # Se forem necessários, precisam ser adicionados aqui e na lógica.

    requestBody:
      description: Parâmetros para listar relações de um objeto (usado se o método for POST).
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - id_objeto # Renomeado de 'id'
              - repository_sparql_endpoint # Renomeado de 'repository'
            properties:
              id_objeto:
                type: string
                format: uri
                description: URI completa do objeto cujas relações serão listadas.
                example: "http://localhost:3030/mydataset#RecursoPrincipal"
              repository_sparql_endpoint:
                type: string
                format: uri
                description: URL do endpoint SPARQL do repositório a ser consultado.
                example: "http://localhost:3030/mydataset/sparql"
              # keyword: # Se necessário, adicionar
              #   type: string
              #   description: "Palavra-chave para filtro (uso a ser definido)."
              #   example: "associatedMedia"
              # type: # Se necessário, adicionar
              #   type: string
              #   description: "Tipo de relação a ser filtrada (uso a ser definido)."
              #   example: "rdf:type"
    responses:
      200:
        description: Lista de relações (triplas) encontradas para o objeto.
        content:
          application/json:
            schema: # Schema para resultado JSON SPARQL padrão
              type: object
              properties:
                head:
                  type: object
                  properties:
                    vars:
                      type: array
                      items:
                        type: string
                      example: ["id", "propriedade", "valor", "tipo_recurso", "titulo"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object
                        properties:
                          id: {"type": "object", "properties": {"type": {"type": "string", "example": "uri"}, "value": {"type": "string", "format": "uri", "example": "http://localhost:3030/mydataset#RecursoPrincipal"}}}
                          propriedade: {"type": "object", "properties": {"type": {"type": "string", "example": "uri"}, "value": {"type": "string", "format": "uri", "example": "http://purl.org/dc/terms/title"}}}
                          valor: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Título do Recurso"}}}
                          tipo_recurso: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Literal"}}}
                          titulo: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Título do Recurso Relacionado"}}, "nullable": true}
      400:
        description: Requisição inválida (ex parâmetros obrigatórios ausentes).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Invalid input"}
                message: {"type": "string", "example": "Campo 'id_objeto' é obrigatório."}
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

    object_uri_param = data.get('id_objeto') # Renomeado de 'id'
    repo_sparql_endpoint = data.get('repository_sparql_endpoint') # Renomeado de 'repository'
    # keyword = data.get('keyword') # Não usado na query atual
    # type_param = data.get('type') # Não usado na query atual

    if not object_uri_param:
        return jsonify({"error": 'Invalid input', "message": "Campo 'id_objeto' (URI do objeto) é obrigatório."}), 400
    if not repo_sparql_endpoint:
        return jsonify({"error": 'Invalid input', "message": "Campo 'repository_sparql_endpoint' é obrigatório."}), 400
    
    # A query SPARQL espera que object_uri_param seja uma URI completa.
    # Não é necessário construir PREFIX : <{repo_sparql_endpoint}#> para esta query específica.
    
    sparql_query = get_prefix() + f"""
        SELECT ?id ?propriedade ?valor  
            (IF(isURI(?valor), "URI", "Literal") AS ?tipo_recurso)
            ?titulo
        WHERE {{
        {{
            # Relações diretas
            ?id ?propriedade ?valor .
            FILTER(?id = <{object_uri_param}>)
        }}
        UNION
        {{
            # Relações inversas
            ?valor ?propriedade ?id .
            FILTER(?id = <{object_uri_param}>)
            # BIND("inversa" AS ?direcao) # direcao não está no SELECT original
        }}
        OPTIONAL {{
            ?valor dc:title ?titulo .
            FILTER(isURI(?valor))
            # BIND("direta" AS ?direcao_titulo) # direcao_titulo não está no SELECT original
        }}
        }}
    """
    current_app.logger.debug(f"SPARQL list_relations query: {sparql_query}")

    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
               'Accept': 'application/sparql-results+json,*/*;q=0.9',
               'X-Requested-With': 'XMLHttpRequest'}
    payload_query = {'query': sparql_query} # Renomeado para evitar conflito
    encoded_payload = urlencode(payload_query)
    
    try:
        response = requests.post(repo_sparql_endpoint, headers=headers, data=encoded_payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        return jsonify(result)
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL query failed for list_relations: {http_err} - Response: {response.text}")
        return jsonify({"error": f"SPARQL query failed with status {response.status_code}", "message": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for list_relations: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in list_relations: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@relationapi_app.route('/add', methods=['POST'])
@token_required
def add_rdf_relation(): # Renomeado de 'add'
    """
    Adiciona uma nova relação RDF (tripla s-p-o) a um repositório.
    O sujeito é identificado por um ID local e uma URI base do repositório.
    O predicado e o objeto (se URI) devem ser URIs completas.
    ---
    tags:
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
              - sujeito_id_local # ID local do sujeito
              - predicado_uri # URI completa do predicado
              - valor_objeto # URI completa ou Literal RDF para o objeto
              - tipo_valor_objeto # "URI" ou "Literal"
              - repository_update_url # Endpoint de update
              - repository_base_uri # URI base para montar a URI do sujeito
            properties:
              sujeito_id_local:
                type: string
                description: ID local do recurso sujeito (será prefixado com repository_base_uri).
                example: "ObjetoRecemCriado123"
              predicado_uri:
                type: string
                format: uri
                description: URI completa da propriedade (predicado).
                example: "http://purl.org/dc/terms/title"
              valor_objeto:
                type: string
                description: Valor da propriedade. Se tipo_valor_objeto for "URI", deve ser uma URI completa. Se "Literal", o valor literal (ex "Meu Título", "true", "123").
                example: "Título Principal do Objeto" # Para Literal
                # example: "http://example.org/relatedResource" # Para URI
              tipo_valor_objeto:
                type: string
                description: Indica se o 'valor_objeto' é uma "URI" ou um "Literal".
                enum: ["URI", "Literal"]
                example: "Literal"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização do repositório.
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base do repositório (ex http://meudominio.com/objetos#) para montar a URI do sujeito.
                example: "http://localhost:3030/mydataset#"
              # 'complemento' e 'prefixo' do request original não parecem ser usados de forma genérica.
              # Se 'complemento' fosse para datatype/langtag de literal, deveria ser parte de 'valor_objeto' ou um campo separado.
              # 'prefixo' para queries SPARQL não se aplica a INSERT DATA simples.
              literal_datatype_uri: # Opcional, para literais tipados
                type: string
                format: uri
                nullable: true
                description: "URI do tipo de dado para o literal (ex http://www.w3.org/2001/XMLSchema#string, ...#integer, ...#boolean, ...#date)."
                example: "http://www.w3.org/2001/XMLSchema#string"
              literal_lang_tag: # Opcional, para literais com tag de idioma
                type: string
                nullable: true
                description: "Tag de idioma para o literal (ex pt, en, es)."
                example: "pt-BR"

    responses:
      201:
        description: Relação (tripla) adicionada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relação adicionada com sucesso"}
                sujeito_uri: {"type": "string", "format": "uri"}
                tripla_adicionada: {"type": "string", "example": "<subj> <pred> <obj> ."}
      400:
        description: Requisição inválida (ex campos obrigatórios ausentes, tipo_valor_objeto inválido).
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['sujeito_id_local', 'predicado_uri', 'valor_objeto', 
                       'tipo_valor_objeto', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data or data[field] is None: # Checa também por None
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    repo_base_uri = data['repository_base_uri']
    if not repo_base_uri.endswith(('#', '/')):
        repo_base_uri += "#"
    
    sujeito_uri_completa = f"<{repo_base_uri}{data['sujeito_id_local']}>"
    predicado_uri_completa = f"<{data['predicado_uri']}>" # Assume que já vem com <> ou é URI nua
    
    valor_obj_str = data['valor_objeto']
    tipo_valor = data['tipo_valor_objeto'].upper() # Normaliza para URI ou LITERAL

    objeto_sparql_formatado = ""
    if tipo_valor == "URI":
        objeto_sparql_formatado = f"<{valor_obj_str}>"
    elif tipo_valor == "LITERAL":
        # Escapar aspas dentro do literal
        valor_literal_escapado = valor_obj_str.replace('"', '\\"')
        objeto_sparql_formatado = f'"{valor_literal_escapado}"' # Aspas duplas para literal
        
        datatype_uri = data.get('literal_datatype_uri')
        lang_tag = data.get('literal_lang_tag')

        if datatype_uri and lang_tag:
            return jsonify({"error": "Invalid input", "message": "Não pode fornecer 'literal_datatype_uri' e 'literal_lang_tag' simultaneamente para um literal."}), 400
        if datatype_uri:
            objeto_sparql_formatado += f"^^<{datatype_uri}>"
        elif lang_tag:
            objeto_sparql_formatado += f"@{lang_tag}"
    else:
        return jsonify({"error": "Invalid input", "message": "Campo 'tipo_valor_objeto' deve ser 'URI' ou 'Literal'."}), 400

    sparql_update_url = data['repository_update_url']
                
    sparql_query = f"""{get_prefix()}
        INSERT DATA {{
            {sujeito_uri_completa} {predicado_uri_completa} {objeto_sparql_formatado} .
        }}"""
    current_app.logger.debug(f"SPARQL add_rdf_relation query: {sparql_query}")

    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        return jsonify({
            "message": "Relação adicionada com sucesso", 
            "sujeito_uri": sujeito_uri_completa.strip("<>"),
            "tripla_adicionada": f"{sujeito_uri_completa} {predicado_uri_completa} {objeto_sparql_formatado} ."
        }), 201
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for add_rdf_relation: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for add_rdf_relation: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in add_rdf_relation: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@relationapi_app.route('/delete_all_relations', methods=['DELETE','POST']) # Renomeado de '/delete'
@token_required
def delete_all_relations_of_object(): # Renomeado de 'remove'
    """
    Remove TODAS as triplas (relações) onde um recurso específico é o SUJEITO.
    Use com CUIDADO, pois isso remove todas as propriedades diretas do objeto.
    ---
    tags:
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
              - object_uri_to_clear # URI completa do objeto
              - repository_update_url
            properties:
              object_uri_to_clear:
                type: string
                format: uri
                description: URI completa do objeto cujas relações (como sujeito) serão removidas.
                example: "http://localhost:3030/mydataset#ObjetoComMuitasPropriedades"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização.
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Todas as relações (como sujeito) do objeto foram removidas com sucesso (ou o objeto não tinha relações/não existia).
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relações do objeto como sujeito foram removidas."}
                object_uri: {"type": "string", "format": "uri"}
      400:
        description: Requisição inválida.
      404:
        description: Objeto não encontrado (se verificação for implementada).
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    object_uri = data.get('object_uri_to_clear')
    sparql_update_url = data.get('repository_update_url') # No original era 'repository'

    if not object_uri or not sparql_update_url:
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_clear' e 'repository_update_url' são obrigatórios."}), 400
        
    obj_uri_sparql = f"<{object_uri}>" # O original usava :objeto_id, o que implica uma base URI. Agora esperamos URI completa.
    
    # Query para deletar todas as triplas onde o objeto é SUJEITO.
    # A query original era DELETE WHERE { :{objeto_id} ?p ?o . }
    sparql_query = f"""{get_prefix()}
        DELETE WHERE {{
            {obj_uri_sparql} ?p ?o .
        }}
    """
    current_app.logger.debug(f"SPARQL delete_all_relations_of_object query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        return jsonify({"message": "Relações do objeto como sujeito foram removidas.", "object_uri": object_uri}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for delete_all_relations: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for delete_all_relations: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in delete_all_relations: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500

    
@relationapi_app.route('/remover_relacao_especifica', methods=['DELETE']) # Renomeado de '/remover_relacao' e método único DELETE
@token_required
def remove_specific_relation(): # Renomeado de 'remover_relacao'
    """
    Remove uma relação RDF específica (uma única tripla s-p-o) de um repositório SPARQL.
    ---
    tags:
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
                description: "URI completa do sujeito da tripla (ex <http://example.org/s1>)."
                example: "<http://localhost:3030/mydataset#RecursoA>"
              p:
                type: string
                description: "URI completa do predicado da tripla (ex <http://purl.org/dc/terms/title>)."
                example: "<http://purl.org/dc/terms/title>"
              o:
                type: string
                description: 'URI completa ou Literal RDF do objeto da tripla (exemplo: <http://example.org/o1> ou "Literal Exemplo").' # CORRIGIDO
                example: '"Literal Exemplo"' #
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
    responses:
      200:
        description: Relação específica removida com sucesso (ou não existia).
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Relação específica excluída com sucesso"}
                triple_removed: {"type": "string", "example": "<subj> <pred> <obj> ."}
      400:
        description: Requisição inválida.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    s_uri = data.get('s') # Sujeito - espera URI completa <...>
    p_uri = data.get('p') # Predicado - espera URI completa <...>
    o_val = data.get('o') # Objeto - espera URI completa <...> ou Literal "..."^^<...>
    sparql_update_url = data.get('repository_update_url') # No original era 'repository'

    if not all([s_uri, p_uri, o_val, sparql_update_url]):
        return jsonify({"error": "Invalid input", "message": "Campos 's', 'p', 'o' e 'repository_update_url' são obrigatórios."}), 400
    
    # A query original usava DELETE WHERE { {s} {p} {o} . }
    # DELETE DATA é mais apropriado para remover uma tripla específica conhecida.
    sparql_query = f"""{get_prefix()}
        DELETE DATA {{
            {s_uri} {p_uri} {o_val} .
        }}
    """
    current_app.logger.debug(f"SPARQL remove_specific_relation query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload_data = {'update': sparql_query} # Renomeado
    encoded_payload = urlencode(payload_data)

    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_payload, timeout=10)
        response.raise_for_status()
        return jsonify({"message": "Relação específica excluída com sucesso", "triple_removed": f"{s_uri} {p_uri} {o_val} ."}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for remove_specific_relation: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for remove_specific_relation: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in remove_specific_relation: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500

    
@relationapi_app.route('/update_properties', methods=['PUT','POST']) # Renomeado de '/update'
@token_required
def update_object_core_properties(): # Renomeado de 'update'
    """
    Atualiza as propriedades dc:description, dc:title e dc:subject (resumo) de um objeto RDF.
    As propriedades antigas são removidas e as novas são inseridas.
    ---
    tags:
      - Relações # Ou talvez "Metadados de Objeto" se for mais apropriado
      - Objetos Digitais # Ou a tag do tipo de objeto que está sendo atualizado
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - object_uri_to_update # URI completa do objeto
              - titulo # Novo título
              - resumo # Novo resumo (dc:subject)
              - repository_update_url
            properties:
              object_uri_to_update:
                type: string
                format: uri
                description: "URI completa do objeto a ser atualizado."
                example: "http://localhost:3030/mydataset#MeuRecurso1"
              descricao: # Opcional, se fornecido, atualiza dc:description
                type: string
                nullable: true # Permite remover se enviado como null ou string vazia
                description: "Nova descrição para o objeto (opcional)."
                example: "Descrição atualizada e mais completa do recurso."
              titulo:
                type: string
                description: "Novo título (dc:title) para o objeto."
                example: "Título Revisado do Recurso"
              resumo: # No original, era dc:subject. dc:abstract é mais comum para resumo.
                      # Mantendo dc:subject conforme original, mas considerar dc:abstract.
                type: string
                description: "Novo resumo/assunto (dc:subject) para o objeto."
                example: "Este recurso trata de aspectos revisados sobre X e Y."
              repository_update_url:
                type: string
                format: uri
                description: "URL do endpoint SPARQL de atualização."
                example: "http://localhost:3030/mydataset/update"
              # 'id' e 'tipo' do request original não são usados diretamente na query SPARQL deste endpoint.
              # 'repository' foi renomeado para 'repository_update_url'.
    responses:
      200:
        description: Propriedades do objeto atualizadas com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {"type": "string", "example": "Propriedades do objeto atualizadas com sucesso"}
                object_uri: {"type": "string", "format": "uri"}
      400:
        description: Requisição inválida.
      404:
        description: Objeto não encontrado para atualização.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    obj_uri_param = data.get('object_uri_to_update') # Espera URI completa
    sparql_update_url = data.get('repository_update_url')
    new_title = data.get('titulo')
    new_subject = data.get('resumo') # Mapeado para dc:subject na query original

    if not all([obj_uri_param, sparql_update_url, new_title, new_subject]):
        return jsonify({"error": "Invalid input", "message": "Campos 'object_uri_to_update', 'repository_update_url', 'titulo' e 'resumo' são obrigatórios."}), 400
    
    obj_uri_sparql = f"<{obj_uri_param}>"
    
    # Cláusulas DELETE e INSERT
    delete_clauses = [
        f"{obj_uri_sparql} dc:title ?oldTitle .",
        f"{obj_uri_sparql} dc:subject ?oldSubject ."
    ]
    insert_clauses = [
        f"{obj_uri_sparql} dc:title \"\"\"{new_title.replace('"""', '\\"""')}\"\"\" ;", # ; no final se houver mais
        f"               dc:subject \"\"\"{new_subject.replace('"""', '\\"""')}\"\"\""
    ]
    where_clauses = [ # Para garantir que os OPTIONALs funcionem
        f"{obj_uri_sparql} ?anyProp ?anyVal .", # Garante que o objeto existe
        f"OPTIONAL {{ {obj_uri_sparql} dc:title ?oldTitle . }}",
        f"OPTIONAL {{ {obj_uri_sparql} dc:subject ?oldSubject . }}"
    ]

    if 'descricao' in data: # Se 'descricao' for fornecida, atualiza dc:description
        delete_clauses.append(f"{obj_uri_sparql} dc:description ?oldDescription .")
        where_clauses.append(f"OPTIONAL {{ {obj_uri_sparql} dc:description ?oldDescription . }}")
        if data['descricao'] is not None and data['descricao'].strip() != "":
            # Adiciona à lista de insert, removendo o ; do último item e adicionando ao novo
            if insert_clauses[-1].endswith(" ."): insert_clauses[-1] = insert_clauses[-1][:-2] + " ;"
            elif not insert_clauses[-1].endswith(" ;"): insert_clauses[-1] += " ;"
            insert_clauses.append(f"               dc:description \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\"")
    
    # Adiciona ponto final à última cláusula de insert
    if insert_clauses:
      if insert_clauses[-1].endswith(" ;"): insert_clauses[-1] = insert_clauses[-1][:-2] + " ."
      elif not insert_clauses[-1].endswith(" ."): insert_clauses[-1] += " ."


    sparql_query = f"""{get_prefix()}
        DELETE {{
            { " ".join(delete_clauses) }
        }}
        INSERT {{
            { " ".join(insert_clauses) }
        }}
        WHERE {{
            { " ".join(where_clauses) }
        }}
    """
    current_app.logger.debug(f"SPARQL update_object_core_properties query: {sparql_query}")
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    payload_data = {'update': sparql_query} # Renomeado
    encoded_payload = urlencode(payload_data)
         
    try:
        response = requests.post(sparql_update_url, headers=headers, data=encoded_payload, timeout=10)
        response.raise_for_status()
        return jsonify({"message": "Propriedades do objeto atualizadas com sucesso", "object_uri": obj_uri_param}), 200
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"SPARQL update failed for update_object_core_properties: {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Error", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException for update_object_core_properties: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in update_object_core_properties: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500
    

# A rota /add_relation original foi movida para /add (renomeada para add_rdf_relation)
# A função add_relation que existia no final do arquivo original era uma cópia da lógica de /add
# e não era um endpoint HTTP. Se for uma função helper, deve ser nomeada com _ e não ter rota.
# Se for para ser um endpoint, precisa de @relationapi_app.route(...) e anotações.
# Assumindo que a funcionalidade de adicionar relação genérica já está coberta por /add_rdf_relation

