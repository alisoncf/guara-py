from flask import Blueprint, request, jsonify, current_app # Adicionado current_app para logging
import requests
# from consultas import get_sparq_class, get_prefix # get_prefix não é usado aqui.
from consultas import get_sparq_class
from config_loader import load_config # Não usado diretamente neste arquivo, mas pode ser para URLs de config
from urllib.parse import urlencode

classapi_app = Blueprint('classapi_app', __name__)

# Supondo que load_config() e as URLs do Fuseki sejam gerenciadas de forma centralizada
# ou passadas para as funções que fazem as chamadas HTTP, se necessário.
# Por ora, o código original não usa config_loader diretamente aqui.

@classapi_app.route('/list', methods=['POST', 'GET'])
def list_classes(): # Renomeado de 'list' para evitar conflito com built-in
    """
    Lista classes de um repositório SPARQL com base em uma palavra-chave.
    Este endpoint suporta GET (com query parameters) e POST (com JSON body).
    A documentação abaixo foca no método POST. Para GET, use os mesmos parâmetros como query strings.
    ---
    tags:
      - Classes
    parameters:
      - name: keyword
        in: query
        required: false # O código original não trata keyword como obrigatório para GET, mas a query sim
        description: Palavra-chave para filtrar as classes (usado se o método for GET).
        schema:
          type: string
        example: "Pessoa"
      - name: repository
        in: query
        required: true # O código original trata repository como obrigatório
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:7200/repositories/ontologia" # Exemplo do original
      - name: orderby
        in: query
        required: false
        description: "Campo para ordenação dos resultados (ex label, class). Default 'class' (usado se o método for GET)."
        schema:
          type: string
        example: "label"
    requestBody:
      description: Parâmetros para busca de classes (usado se o método for POST).
      required: true # O corpo é necessário para POST
      content:
        application/json:
          schema:
            type: object
            required:
              - repository
            properties:
              keyword:
                type: string
                description: Palavra-chave para filtrar as classes.
                example: "Animal"
              repository:
                type: string
                format: uri
                description: URL do endpoint SPARQL do repositório.
                example: "http://localhost:7200/repositories/ontologia" # Exemplo do original
              orderby:
                type: string
                description: "Campo para ordenação dos resultados (ex label, class). Default 'class'."
                example: "label"
    responses:
      200:
        description: Lista de classes encontrada com sucesso.
        content:
          application/json:
            schema:
              type: object # O resultado é um JSON SPARQL padrão
              properties:
                head:
                  type: object
                  properties:
                    vars:
                      type: array
                      items:
                        type: string
                      example: ["class", "label", "description", "subclassof"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object
                        properties:
                          class:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "uri"
                              value:
                                type: string
                                format: uri
                                example: "http://example.org/ontology#Animal"
                          label:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "literal"
                              value:
                                type: string
                                example: "Animal"
                          description:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "literal"
                              value:
                                type: string
                                example: "Representa um ser do reino animal."
                          subclassof:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "uri"
                              value:
                                type: string
                                format: uri
                                example: "http://example.org/ontology#LivingBeing"
      400:
        description: "Requisição inválida (ex parâmetro 'repository' ausente ou formato incorreto)." # CORRIGIDO
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid input"
                message:
                  type: string
                  example: "Expected JSON with 'repository' field"
      500:
        description: Erro interno no servidor ou falha na comunicação com o endpoint SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "RequestException"
                message:
                  type: string
                  example: "Connection refused"
    """
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid input", "message": "Request body cannot be empty for POST"}), 400
    elif request.method == 'GET':
        data = request.args
        if not data.get('repository'): # Repositório é crucial
             return jsonify({"error": "Invalid input", "message": "Query parameter 'repository' is required for GET"}), 400
    else:
        return jsonify({"error": "Method Not Allowed"}), 405

    keyword = data.get('keyword', '') # Default para string vazia se não fornecido
    repo = data.get('repository')
    orderby = data.get('orderby', 'class') # Default 'class'

    if not repo: # Checagem dupla, mas importante
        return jsonify({"error": 'Invalid input', "message": "Field 'repository' is required"}), 400

    sparqapi_url = repo # A URL do repositório é o endpoint SPARQL

    try:
        sparql_query = get_sparq_class().replace(
            '%keyword%', keyword).replace('%orderby%', orderby)

        headers = {
            'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8",
            'Accept': "application/sparql-results+json,*/*;q=0.9", # Aceita JSON
            'X-Requested-With': 'XMLHttpRequest'
        }
        payload = {'query': sparql_query}
        encoded_data = urlencode(payload)

        current_app.logger.debug(f"Querying {sparqapi_url} with query: {sparql_query}")
        response = requests.post(sparqapi_url, headers=headers, data=encoded_data, timeout=10) # Sempre POST para endpoint SPARQL

        if response.status_code == 200:
            result = response.json()
            return jsonify(result)
        else:
            current_app.logger.error(f"Erro na consulta SPARQL: {response.status_code} - {response.text}") # Log do erro
            return jsonify({"error": f"SPARQL query failed with status {response.status_code}", "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro de requisição: {str(e)}") # Log do erro
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except KeyError as e: # Pode ocorrer se data.get falhar e não for tratado
        current_app.logger.error(f"Erro de chave: {str(e)}") # Log do erro
        return jsonify({"error": "KeyError", "message": f"Missing expected field: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado: {str(e)}") # Log do erro
        return jsonify({"error": "Exception", "message": str(e)}), 500


@classapi_app.route('/adicionar_classe', methods=['POST'])
def adicionar_classe():
    """
    Adiciona uma nova classe a um repositório SPARQL.
    ---
    tags:
      - Classes
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - label
              - comment
              - subclassof_localname # Alterado para clareza
              - repository_update_url # Alterado para clareza
              - repository_base_uri # Necessário para construir a URI da classe
            properties:
              label:
                type: string
                description: Rótulo (nome legível) da nova classe.
                example: "Veículo Terrestre"
              comment:
                type: string
                description: Descrição ou comentário sobre a nova classe.
                example: "Classe para representar veículos que se movem em terra."
              subclassof_localname:
                type: string
                description: Nome local (sem prefixo) da superclasse. A superclasse deve existir no mesmo base URI.
                example: "Veiculo"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização do repositório.
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base da ontologia no repositório (ex http://meudominio.com/ontologia#).
                example: "http://example.org/ontology#"
    responses:
      201:
        description: Classe adicionada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Classe adicionada com sucesso"
                class_uri:
                  type: string
                  format: uri
                  example: "http://example.org/ontology#VeiculoTerrestre"
                label:
                  type: string
                  example: "Veículo Terrestre"
      400:
        description: Requisição inválida (ex campos obrigatórios ausentes ou malformados).
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid input"
                message:
                  type: string
                  example: "Campo 'label' é obrigatório."
      500:
        description: Erro interno no servidor ou falha ao executar a atualização SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "SPARQL Update Failed"
                message:
                  type: string
                  example: "Detalhes do erro do servidor Fuseki."
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['label', 'comment', 'subclassof_localname', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    label = data['label']
    comment = data['comment']
    subclassof_localname = data['subclassof_localname']
    sparql_update_url = data['repository_update_url']
    repository_base_uri = data['repository_base_uri']

    # Garantir que a base URI termina com # ou /
    if not repository_base_uri.endswith(('#', '/')):
        repository_base_uri += "#"

    nome_classe_uri_part = label.replace(" ", "_").replace("-", "_") # Sanitização básica para URI
    class_uri_completa = f"<{repository_base_uri}{nome_classe_uri_part}>"
    subclassof_uri_completa = f"<{repository_base_uri}{subclassof_localname}>"


    # Escapar aspas triplas dentro do comentário, se houver.
    escaped_comment = comment.replace('"""', '\\"""')

    sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        INSERT DATA {{
            {class_uri_completa} rdf:type owl:Class ;
                        rdfs:label "{label}" ;
                        rdfs:comment \"\"\"{escaped_comment}\"\"\" ;
                        rdfs:subClassOf {subclassof_uri_completa} .
        }}
    """

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': "application/sparql-results+json,*/*;q=0.9", # Embora não seja uma query, é um padrão
        'X-Requested-With': 'XMLHttpRequest'
    }
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        current_app.logger.debug(f"Updating {sparql_update_url} with query: {sparql_query}")
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)

        if response.status_code == 200 or response.status_code == 204: # 204 No Content também é sucesso para updates
            return jsonify({
                "message": "Classe adicionada com sucesso",
                "class_uri": class_uri_completa.strip('<>'), # Remove <> para o exemplo
                "label": label
            }), 201
        else:
            current_app.logger.error(f"Erro ao adicionar classe: {response.status_code} - {response.text}")
            return jsonify({"error": f"SPARQL Update Failed with status {response.status_code}", "message": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro de requisição ao adicionar classe: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Erro inesperado ao adicionar classe: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@classapi_app.route('/alterar_classe', methods=['POST']) # POST é comum para Update se não for idempotente ou se for complexo
def alterar_classe():
    """
    Altera uma classe existente em um repositório SPARQL.
    ---
    tags:
      - Classes
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - class_uri # URI completa da classe a ser alterada
              - new_label
              - new_comment
              - new_subclassof_localname
              - repository_update_url
              - repository_base_uri
            properties:
              class_uri:
                type: string
                format: uri
                description: URI completa da classe a ser alterada.
                example: "http://example.org/ontology#MinhaClasseAntiga"
              new_label:
                type: string
                description: Novo rótulo (nome legível) para a classe.
                example: "Minha Classe Atualizada"
              new_comment:
                type: string
                description: Nova descrição ou comentário para a classe.
                example: "Esta classe foi atualizada para refletir novas definições."
              new_subclassof_localname:
                type: string
                description: Nome local (sem prefixo) da nova superclasse.
                example: "OutraSuperClasse"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização do repositório.
                example: "http://localhost:3030/mydataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base da ontologia no repositório.
                example: "http://example.org/ontology#"
    responses:
      200:
        description: Classe alterada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Classe alterada com sucesso"
                class_uri:
                  type: string
                  format: uri
                  example: "http://example.org/ontology#MinhaClasseAntiga"
      400:
        description: Requisição inválida (ex campos obrigatórios ausentes ou URI malformada).
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid input"
                message:
                  type: string
                  example: "Campo 'class_uri' é obrigatório."
      404:
        description: Classe a ser alterada não encontrada.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Not Found"
                message:
                  type: string
                  example: "Classe não encontrada para alteração."
      500:
        description: Erro interno no servidor ou falha ao executar a atualização SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "SPARQL Update Failed"
                message:
                  type: string
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['class_uri', 'new_label', 'new_comment', 'new_subclassof_localname', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    class_uri_to_alter = f"<{data['class_uri']}>" # Envolve com <> para SPARQL
    new_label = data['new_label']
    new_comment = data['new_comment']
    new_subclassof_localname = data['new_subclassof_localname']
    sparql_update_url = data['repository_update_url']
    repository_base_uri = data['repository_base_uri']

    if not repository_base_uri.endswith(('#', '/')):
        repository_base_uri += "#"
    
    new_subclassof_uri_completa = f"<{repository_base_uri}{new_subclassof_localname}>"
    escaped_new_comment = new_comment.replace('"""', '\\"""')

    # Primeiro, verificar se a classe existe pode ser uma boa prática (não implementado aqui para manter similar ao original)

    sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        DELETE {{
            {class_uri_to_alter} rdfs:label ?oldLabel ;
                        rdfs:comment ?oldComment ;
                        rdfs:subClassOf ?oldSubclass .
        }}
        INSERT {{
            {class_uri_to_alter} rdfs:label "{new_label}" ;
                        rdfs:comment \"\"\"{escaped_new_comment}\"\"\" ;
                        rdfs:subClassOf {new_subclassof_uri_completa} .
        }}
        WHERE {{
            {class_uri_to_alter} rdf:type owl:Class . # Garante que estamos alterando uma classe
            OPTIONAL {{ {class_uri_to_alter} rdfs:label ?oldLabel . }}
            OPTIONAL {{ {class_uri_to_alter} rdfs:comment ?oldComment . }}
            OPTIONAL {{ {class_uri_to_alter} rdfs:subClassOf ?oldSubclass . }}
        }}
    """

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': "application/sparql-results+json,*/*;q=0.9",
        'X-Requested-With': 'XMLHttpRequest'
    }
    payload = {'update': sparql_query}
    encoded_data = urlencode(payload)

    try:
        current_app.logger.debug(f"Alterando classe em {sparql_update_url} com query: {sparql_query}")
        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)

        if response.status_code == 200 or response.status_code == 204:
            # Para verificar se algo foi realmente alterado, seria necessário uma query ASK ou SELECT antes
            # ou analisar a resposta do Fuseki se ela indicar o número de triplas alteradas.
            # Por simplicidade, assumimos sucesso se o update não der erro.
            return jsonify({
                "message": "Classe alterada com sucesso",
                "class_uri": data['class_uri']
            }), 200
        else:
            current_app.logger.error(f"Erro ao alterar classe: {response.status_code} - {response.text}")
            return jsonify({"error": f"SPARQL Update Failed with status {response.status_code}", "message": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro de requisição ao alterar classe: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Erro inesperado ao alterar classe: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@classapi_app.route('/excluir_classe', methods=['DELETE', 'POST']) # Manter POST se necessário, mas DELETE é mais semântico
def excluir_classe():
    """
    Exclui uma classe de um repositório SPARQL.
    Requer a URI completa da classe e a URL do endpoint de atualização do repositório.
    A exclusão falhará (com código 400 ou 409) se a classe for uma superclasse de outras classes.
    ---
    tags:
      - Classes
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - class_uri_to_delete
              - repository_update_url
              - repository_query_url # Necessário para verificar subclasses
            properties:
              class_uri_to_delete:
                type: string
                format: uri
                description: URI completa da classe a ser excluída.
                example: "http://example.org/ontology#ClasseParaExcluir"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de atualização.
                example: "http://localhost:3030/mydataset/update"
              repository_query_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de consulta (para checagens).
                example: "http://localhost:3030/mydataset/sparql"
    responses:
      200:
        description: Classe excluída com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Classe excluída com sucesso"
                class_uri:
                  type: string
                  format: uri
                  example: "http://example.org/ontology#ClasseParaExcluir"
      400:
        description: Requisição inválida ou a classe não pode ser excluída (ex é superclasse).
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Deletion Constraint Violated"
                message:
                  type: string
                  example: "Existem subclasses relacionadas a esta classe. Não pode ser excluída."
      404:
        description: Classe não encontrada para exclusão.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Not Found"
                message:
                  type: string
                  example: "Classe não encontrada."
      500:
        description: Erro interno no servidor ou falha na comunicação SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "SPARQL Error"
                message:
                  type: string
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['class_uri_to_delete', 'repository_update_url', 'repository_query_url']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    class_uri_param = data['class_uri_to_delete']
    class_uri_sparql = f"<{class_uri_param}>" # Envolve com <>
    sparql_update_url = data['repository_update_url']
    sparql_query_url = data['repository_query_url']


    # Verificar se a classe a ser excluída é superclasse de alguma outra
    # Esta é uma verificação de restrição de integridade lógica
    try:
        has_subclasses = verificar_existencia_subclasse(class_uri_param, sparql_query_url)
        if has_subclasses:
            return jsonify({
                "error": "Deletion Constraint Violated",
                "message": "Existem subclasses relacionadas a esta classe. Não pode ser excluída."
            }), 400 # Ou 409 Conflict
    except Exception as e:
        current_app.logger.error(f"Erro ao verificar subclasses: {str(e)}")
        return jsonify({"error": "SPARQL Query Error", "message": f"Erro ao verificar subclasses: {str(e)}"}), 500

    # Query para deletar todas as triplas onde a classe é sujeito
    # (definição da classe: label, comment, subClassOf, type owl:Class)
    # E também onde ela é objeto (se alguma propriedade aponta para ela como range, etc.,
    # mas isso é mais complexo e geralmente tratado por inferência ou regras específicas)
    # Esta query foca em remover a definição da classe em si.
    sparql_delete_query = f"""
        DELETE WHERE {{
            {class_uri_sparql} ?p ?o .
        }}
    """
    # Adicionalmente, se quiser remover triplas onde a classe é usada como rdfs:subClassOf por outras:
    # (Isso pode ser perigoso se não for o desejado, pois "orfana" subclasses)
    # sparql_delete_subclass_references = f"""
    # DELETE WHERE {{
    # ?s rdfs:subClassOf {class_uri_sparql} .
    # }}
    # """

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': "application/sparql-results+json,*/*;q=0.9",
        'X-Requested-With': 'XMLHttpRequest'
    }
    payload_delete = {'update': sparql_delete_query}
    encoded_data_delete = urlencode(payload_delete)

    try:
        current_app.logger.debug(f"Excluindo classe em {sparql_update_url} com query: {sparql_delete_query}")
        response_delete = requests.post(sparql_update_url, headers=headers, data=encoded_data_delete, timeout=10)

        if response_delete.status_code == 200 or response_delete.status_code == 204:
            # Seria bom verificar se a classe existia antes de tentar excluir para retornar 404 apropriadamente.
            # A verificação de subclasses já meio que implica existência, mas não garante.
            return jsonify({"message": "Classe excluída com sucesso", "class_uri": class_uri_param}), 200
        else:
            current_app.logger.error(f"Erro ao excluir classe: {response_delete.status_code} - {response_delete.text}")
            return jsonify({
                "error": f"SPARQL Update Failed with status {response_delete.status_code}",
                "message": response_delete.text
            }), response_delete.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro de requisição ao excluir classe: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Erro inesperado ao excluir classe: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


def verificar_existencia_subclasse(class_uri_to_check, repository_query_url):
    """
    Verifica se a URI da classe fornecida é usada como rdfs:subClassOf por qualquer outra classe.
    Retorna True se for superclasse de alguma, False caso contrário.
    Lança exceção em caso de erro na query SPARQL.
    """
    class_uri_sparql_format = f"<{class_uri_to_check}>"
    
    sparql_check_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        ASK {{
            ?s rdfs:subClassOf {class_uri_sparql_format} .
            FILTER(?s != {class_uri_sparql_format}) # Para não se contar como subclasse de si mesma se houver loops
        }}
    """
    
    headers = {
        'Accept': 'application/sparql-results+json', # ASK queries retornam JSON com boolean
        'X-Requested-With': 'XMLHttpRequest'
    }
    params = {'query': sparql_check_query}

    current_app.logger.debug(f"Verificando subclasses para {class_uri_to_check} em {repository_query_url} com query: {sparql_check_query}")
    response = requests.get(repository_query_url, headers=headers, params=params, timeout=10)

    if response.status_code == 200:
        result = response.json()
        return result.get('boolean', False) # Retorna o valor booleano do ASK
    else:
        error_message = f"SPARQL ASK query failed: {response.status_code} {response.text}"
        current_app.logger.error(error_message)
        raise Exception(error_message)