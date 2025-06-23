from flask import Blueprint, request, jsonify, current_app
# Removido 'requests' e 'urlencode', pois agora estão no 'utils'
from consultas import get_sparq_class
# Importando as novas funções de utilidade
from utils import execute_sparql_query, execute_sparql_update

classapi_app = Blueprint('classapi_app', __name__)


@classapi_app.route('/list', methods=['POST', 'GET'])
def list_classes():
    """
    Lista classes de um repositório SPARQL com base em uma palavra-chave.
    (A documentação do Swagger permanece a mesma)
    ---
    tags:
      - Classes
    parameters:
      - name: keyword
        in: query
        required: false
        description: Palavra-chave para filtrar as classes (usado se o método for GET).
        schema:
          type: string
        example: "Pessoa"
      - name: repository
        in: query
        required: true
        description: URL do endpoint SPARQL do repositório (usado se o método for GET).
        schema:
          type: string
          format: uri
        example: "http://localhost:7200/repositories/ontologia"
      - name: orderby
        in: query
        required: false
        description: "Campo para ordenação dos resultados (ex label, class). Default 'class' (usado se o método for GET)."
        schema:
          type: string
        example: "label"
    requestBody:
      description: Parâmetros para busca de classes (usado se o método for POST).
      required: true
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
                example: "http://localhost:7200/repositories/ontologia"
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
              type: object
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
      400:
        description: "Requisição inválida (ex parâmetro 'repository' ausente ou formato incorreto)."
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
        if not data.get('repository'):
            return jsonify(
                {"error": "Invalid input", "message": "Query parameter 'repository' is required for GET"}), 400
    else:
        return jsonify({"error": "Method Not Allowed"}), 405

    keyword = data.get('keyword', '')
    repo_endpoint = data.get('repository')
    orderby = data.get('orderby', 'class')

    if not repo_endpoint:
        return jsonify({"error": 'Invalid input', "message": "Field 'repository' is required"}), 400

    try:
        sparql_query = get_sparq_class().replace(
            '%keyword%', keyword).replace('%orderby%', orderby)

        # Usando a nova função centralizada
        result = execute_sparql_query(repo_endpoint, sparql_query)
        return jsonify(result)

    except Exception as e:
        # Erros agora são capturados de forma mais genérica
        # e os detalhes já são logados dentro da função execute_sparql_query
        error_message, details = (e.args if len(e.args) > 1 else (str(e), ''))
        return jsonify({"error": error_message, "message": details}), 500


@classapi_app.route('/adicionar_classe', methods=['POST'])
def adicionar_classe():
    """
    Adiciona uma nova classe a um repositório SPARQL.
    (A documentação do Swagger permanece a mesma)
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
              - subclassof_localname
              - repository_update_url
              - repository_base_uri
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
      500:
        description: Erro interno no servidor ou falha ao executar a atualização SPARQL.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['label', 'comment', 'subclassof_localname', 'repository_update_url', 'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    label = data['label']
    repository_base_uri = data['repository_base_uri']
    if not repository_base_uri.endswith(('#', '/')):
        repository_base_uri += "#"

    nome_classe_uri_part = label.replace(" ", "_").replace("-", "_")
    class_uri_completa = f"<{repository_base_uri}{nome_classe_uri_part}>"
    subclassof_uri_completa = f"<{repository_base_uri}{data['subclassof_localname']}>"
    escaped_comment = data['comment'].replace('"""', '\\"""')

    sparql_update = f"""
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

    try:
        # Usando a nova função centralizada
        execute_sparql_update(data['repository_update_url'], sparql_update)
        return jsonify({
            "message": "Classe adicionada com sucesso",
            "class_uri": class_uri_completa.strip('<>'),
            "label": label
        }), 201
    except Exception as e:
        error_message, details = (e.args if len(e.args) > 1 else (str(e), ''))
        return jsonify({"error": error_message, "message": details}), 500


@classapi_app.route('/alterar_classe', methods=['POST'])
def alterar_classe():
    """
    Altera uma classe existente em um repositório SPARQL.
    (A documentação do Swagger permanece a mesma)
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
              - class_uri
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
      400:
        description: Requisição inválida.
      404:
        description: Classe a ser alterada não encontrada.
      500:
        description: Erro interno no servidor ou falha ao executar a atualização SPARQL.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['class_uri', 'new_label', 'new_comment', 'new_subclassof_localname', 'repository_update_url',
                       'repository_base_uri']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    class_uri_to_alter = f"<{data['class_uri']}>"
    repository_base_uri = data['repository_base_uri']
    if not repository_base_uri.endswith(('#', '/')):
        repository_base_uri += "#"

    new_subclassof_uri_completa = f"<{repository_base_uri}{data['new_subclassof_localname']}>"
    escaped_new_comment = data['new_comment'].replace('"""', '\\"""')

    sparql_update = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        DELETE {{
            {class_uri_to_alter} rdfs:label ?oldLabel ;
                        rdfs:comment ?oldComment ;
                        rdfs:subClassOf ?oldSubclass .
        }}
        INSERT {{
            {class_uri_to_alter} rdfs:label "{data['new_label']}" ;
                        rdfs:comment \"\"\"{escaped_new_comment}\"\"\" ;
                        rdfs:subClassOf {new_subclassof_uri_completa} .
        }}
        WHERE {{
            {class_uri_to_alter} rdf:type owl:Class .
            OPTIONAL {{ {class_uri_to_alter} rdfs:label ?oldLabel . }}
            OPTIONAL {{ {class_uri_to_alter} rdfs:comment ?oldComment . }}
            OPTIONAL {{ {class_uri_to_alter} rdfs:subClassOf ?oldSubclass . }}
        }}
    """
    try:
        # Usando a nova função centralizada
        execute_sparql_update(data['repository_update_url'], sparql_update)
        return jsonify({
            "message": "Classe alterada com sucesso",
            "class_uri": data['class_uri']
        }), 200
    except Exception as e:
        error_message, details = (e.args if len(e.args) > 1 else (str(e), ''))
        return jsonify({"error": error_message, "message": details}), 500


@classapi_app.route('/excluir_classe', methods=['DELETE', 'POST'])
def excluir_classe():
    """
    Exclui uma classe de um repositório SPARQL.
    (A documentação do Swagger permanece a mesma)
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
              - repository_query_url
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
      400:
        description: Requisição inválida ou a classe não pode ser excluída.
      404:
        description: Classe não encontrada para exclusão.
      500:
        description: Erro interno no servidor ou falha na comunicação SPARQL.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

    required_fields = ['class_uri_to_delete', 'repository_update_url', 'repository_query_url']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório."}), 400

    class_uri_param = data['class_uri_to_delete']

    try:
        has_subclasses = verificar_existencia_subclasse(class_uri_param, data['repository_query_url'])
        if has_subclasses:
            return jsonify({
                "error": "Deletion Constraint Violated",
                "message": "Existem subclasses relacionadas a esta classe. Não pode ser excluída."
            }), 400

        sparql_delete_query = f"""
            DELETE WHERE {{
                <{class_uri_param}> ?p ?o .
            }}
        """
        # Usando a nova função centralizada
        execute_sparql_update(data['repository_update_url'], sparql_delete_query)
        return jsonify({"message": "Classe excluída com sucesso", "class_uri": class_uri_param}), 200

    except Exception as e:
        error_message, details = (e.args if len(e.args) > 1 else (str(e), ''))
        return jsonify({"error": error_message, "message": details}), 500


def verificar_existencia_subclasse(class_uri_to_check, repository_query_url):
    """
    Verifica se a URI da classe fornecida é usada como rdfs:subClassOf por qualquer outra classe.
    """
    sparql_check_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        ASK {{
            ?s rdfs:subClassOf <{class_uri_to_check}> .
            FILTER(?s != <{class_uri_to_check}>)
        }}
    """
    try:
        # Usando a nova função centralizada
        result = execute_sparql_query(repository_query_url, sparql_check_query)
        return result.get('boolean', False)
    except Exception as e:
        # Repassa a exceção para ser tratada pela rota principal
        raise e
