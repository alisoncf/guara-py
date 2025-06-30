from flask import Blueprint, request, jsonify, current_app
import uuid
from datetime import datetime, timedelta, timezone
# Importar as funções refatoradas de utils.py
from utils import execute_sparql_query, execute_sparql_update
# Importar o carregador de configuração e obter as URLs
from config_loader import load_config
from blueprints.repositorios import obter_repositorio_por_nome # Supondo que esta função retorne um dicionário com os detalhes do repo

acessoapp = Blueprint('acessoapp', __name__)

# Carregar a configuração uma vez quando o módulo é importado
config = load_config('config.json')
FUSEKI_URL = config.get('user_update_url')
FUSEKI_QUERY_URL = config.get('user_query_url')

@acessoapp.route('/login', methods=['POST'])
def login():
    """
    Realiza o login do usuário apenas com email e senha.
    Após o login, retorna o token de autenticação e os URIs de todos os repositórios associados.
    ---
    tags:
      - Autenticação
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - email
              - password
            properties:
              email:
                type: string
                format: email
                description: Email do usuário para login.
                example: "usuario@dominio.com"
              password:
                type: string
                format: password
                description: Senha do usuário.
                example: "senha123"
    responses:
      200:
        description: Login realizado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Login successful"
                user:
                  type: string
                  description: Nome de usuário (username).
                  example: "curador_exemplo"
                email:
                  type: string
                  format: email
                  example: "usuario@dominio.com"
                permissao:
                  type: string
                  description: Nível de permissão do usuário.
                  example: "admin"
                token:
                  type: string
                  format: uuid
                  description: Token de autenticação JWT para sessões subsequentes.
                  example: "a1b2c3d4-e5f6-7890-1234-567890abcdef"
                repositorios_associados_nomes:
                  type: array
                  items:
                    type: string
                  description: Lista de nomes dos repositórios associados ao usuário.
                  example: ["repositorio-1", "repositorio-2"]
                validade:
                  type: string
                  format: date-time
                  description: Data e hora de expiração do token.
                  example: "2025-05-30T14:30:00Z"
      400:
        description: Requisição mal formatada ou dados ausentes.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Campo 'email' é obrigatório."
      401:
        description: Usuário ou senha inválidos.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Usuário ou senha inválidos"
      500:
        description: Erro interno ao tentar realizar o login ou atualizar o token.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Falha ao conectar ao banco de dados de usuários."
    """
    data = request.json
    if not data:
        return jsonify({'message': 'Corpo da requisição não pode ser vazio.'}), 400

    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'message': 'Campos email e password são obrigatórios.'}), 400

    # Query para buscar usuário, SEM filtrar por nome de repositório no login
    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    SELECT ?s ?permissao ?username ?repositorio_uri WHERE {{
        ?s foaf:mbox "{email}" ;
           foaf:password "{password}" ;
           :temPermissao ?permissao ;
           :repo ?repositorio_uri ; # Busca todos os repositórios associados
           :username ?username .
    }}
    """
    current_app.logger.debug(f"Query Login SPARQL: {query}")

    try:
        results = execute_sparql_query(FUSEKI_QUERY_URL, query)

        if not results or not results.get('results', {}).get('bindings'):
            return jsonify({'message': 'Usuário ou senha inválidos'}), 401

        # Coleta todos os repositórios associados ao usuário
        user_data_bindings = results['results']['bindings']
        user_uri = user_data_bindings[0]['s']['value']
        user_permission = user_data_bindings[0]['permissao']['value']
        user_name = user_data_bindings[0]['username']['value']

        repositorios_associados_nomes = []
        # Percorre todos os bindings para coletar todos os URIs/nomes de repositórios
        for binding in user_data_bindings:
            repo_uri_from_user_db = binding['repositorio_uri']['value']
            # Assumindo que :repo armazena o NOME do repositório (literal)
            repositorios_associados_nomes.append(repo_uri_from_user_db)


        token = str(uuid.uuid4())
        validade = datetime.now(timezone.utc) + timedelta(hours=24)

        update_query = f"""
        PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
        DELETE {{ <{user_uri}> :token ?old_token ; :validade ?old_validade . }}
        INSERT {{ <{user_uri}> :token "{token}" ; :validade "{validade.isoformat()}" . }}
        WHERE {{
            OPTIONAL {{ <{user_uri}> :token ?old_token . }}
            OPTIONAL {{ <{user_uri}> :validade ?old_validade . }}
        }}
        """
        current_app.logger.debug(f"Query Update Token SPARQL: {update_query}")
        execute_sparql_update(FUSEKI_URL, update_query) # Use FUSEKI_URL para updates

        return jsonify({
            'message': 'Login successful',
            'user': user_name,
            'email': email,
            'permissao': user_permission,
            'token': token,
            'repositorios_associados_nomes': list(set(repositorios_associados_nomes)), # Retorna nomes únicos
            'validade': validade.isoformat(),
        }), 200
    except Exception as e:
        current_app.logger.error(f"Erro no login: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@acessoapp.route('/add_user', methods=['POST']) # Rota /add_user, função add_curador
def add_curador():
    """
    Adiciona um novo usuário (curador) ao sistema.
    ---
    tags:
      - Usuários
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - username
              - password
              - permissao
              - email
              - repo_name # Nome do repositório a ser associado
            properties:
              username:
                type: string
                description: Nome de usuário único para o novo curador.
                example: "novo_curador"
              password:
                type: string
                format: password
                description: Senha para o novo curador.
                example: "S3nh@F0rt3!"
              permissao:
                type: string
                description: Nível de permissão (ex admin, editor, leitor).
                example: "editor"
              email:
                type: string
                format: email
                description: Endereço de email do novo curador.
                example: "novo.curador@example.com"
              repo_name:
                type: string
                description: Nome do repositório ao qual este curador será associado.
                example: "repositorio-principal"
    responses:
      201:
        description: Usuário (curador) adicionado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Usuário adicionado com sucesso."
                user_uri:
                  type: string
                  format: uri
                  example: "http://guara.ueg.br/ontologias/usuarios#novo_curador"
      400:
        description: Dados de entrada inválidos ou campos obrigatórios ausentes.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Campo 'username' é obrigatório."
      409: # Conflict - se o usuário já existir
        description: Usuário com este username ou email já existe.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Usuário com este username já existe."
      500:
        description: Erro interno ao adicionar o usuário (curador).
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Falha ao adicionar usuário."
    """
    data = request.json
    if not data:
        return jsonify({'message': 'Corpo da requisição não pode ser vazio.'}), 400

    username = data.get('username')
    password = data.get('password')
    permissao = data.get('permissao')
    email = data.get('email')
    repo_name = data.get('repo_name')

    if not all([username, password, permissao, email, repo_name]):
        return jsonify({'message': 'Campos username, password, permissao, email e repo_name são obrigatórios.'}), 400

    # Opcional: Verificar se o usuário já existe antes de tentar inserir
    # check_query = f"""
    # PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    # PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    # ASK {{
    #     VALUES ?u {{ :{username} }}
    #     ?u rdf:type :Curador .
    #     # Ou verificar por email: ?u foaf:mbox "{email}" .
    # }}
    # """
    # try:
    #     check_results = execute_sparql_query(FUSEKI_QUERY_URL, check_query)
    #     if check_results.get('boolean', False):
    #         return jsonify({'message': f"Usuário com username '{username}' já existe."}), 409
    # except Exception as e:
    #     current_app.logger.error(f"Erro ao verificar existência de usuário: {str(e)}")
    #     # Decide se quer que a falha na verificação impeça a adição. Por enquanto, prossegue.

    user_resource_uri = f":{username}"

    insert_query = f"""
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    INSERT DATA {{
        {user_resource_uri} rdf:type :Curador ;
                   :username "{username}" ;
                   :password "{password}" ;
                   :temPermissao "{permissao}" ;
                   foaf:mbox "{email}" ;
                   :repo "{repo_name}" .
    }}
    """
    current_app.logger.debug(f"Query Insert Usuário SPARQL: {insert_query}")

    try:
        execute_sparql_update(FUSEKI_URL, insert_query) # Use FUSEKI_URL para updates
        base_uri = FUSEKI_QUERY_URL.split('/usuarios/query')[0] + "/usuarios#"
        full_user_uri = base_uri + username
        return jsonify({'message': 'Usuário adicionado com sucesso.', 'user_uri': full_user_uri}), 201
    except Exception as e:
        current_app.logger.error(f"Erro ao adicionar usuário: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
