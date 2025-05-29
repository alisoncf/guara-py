from flask import Blueprint, request, jsonify
import requests
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
from blueprints.repositorios import obter_repositorio_por_nome # Supondo que esta função retorne um dicionário com os detalhes do repo

acessoapp = Blueprint('acessoapp', __name__)

def load_config(filename='config.json'):
    with open(filename, 'r') as f:
        return json.load(f)

config = load_config('config.json')
FUSEKI_URL = config.get('user_update_url')
FUSEKI_QUERY_URL = config.get('user_query_url')

def execute_sparql_update(query):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data_envio = {'update': query}
    encoded_data = urlencode(data_envio)
    response = requests.post(FUSEKI_URL, headers=headers, data=encoded_data)
    return response

def execute_sparql_query(query):
    headers = {'Accept': 'application/sparql-results+json'}
    response = requests.get(FUSEKI_QUERY_URL, params={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        # Adicionar tratamento de erro ou log se necessário
        print(f"Erro na consulta SPARQL: {response.status_code} - {response.text}")
        return {"results": {"bindings": []}} # Retornar estrutura vazia em caso de erro

@acessoapp.route('/login', methods=['POST'])
def login():
    """
    Realiza o login do usuário no repositório solicitado.
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
              - name # Nome do repositório para login
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
              name:
                type: string
                description: Nome do repositório ao qual o usuário deseja se conectar.
                example: "repositorio-1"
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
                  description: Nível de permissão do usuário no repositório.
                  example: "admin"
                token:
                  type: string
                  format: uuid
                  description: Token de autenticação JWT para sessões subsequentes.
                  example: "a1b2c3d4-e5f6-7890-1234-567890abcdef"
                repositorio:
                  type: string
                  description: URI do recurso do repositório associado ao usuário (conforme armazenado no grafo de usuários).
                  example: "http://guara.ueg.br/ontologias/usuarios#repositorio_xyz"
                validade:
                  type: string
                  format: date-time
                  description: Data e hora de expiração do token.
                  example: "2025-05-30T14:30:00Z"
                repositorio_conectado:
                  type: object
                  description: Detalhes do repositório ao qual o login foi efetuado.
                  properties:
                    nome:
                      type: string
                      example: "Repositório Exemplo"
                    uri:
                      type: string
                      format: uri
                      example: "http://localhost:3030/repositorio_exemplo"
                    contato:
                      type: string
                      nullable: true
                      example: "contato@repositorio.org"
                    descricao:
                      type: string
                      nullable: true
                      example: "Este é um repositório de exemplo."
                    responsavel:
                      type: string
                      nullable: true
                      example: "Organização Exemplo"
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
        description: Usuário ou senha inválidos para o repositório especificado.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Usuário ou senha inválidos para esse repositório"
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
    repo_name_param = data.get('name') # Parâmetro 'name' para identificar o repositório

    if not all([email, password, repo_name_param]):
        return jsonify({'message': 'Campos email, password e name (nome do repositório) são obrigatórios.'}), 400

    # Query para buscar usuário, usando :password como definido no TTL
    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    SELECT ?s ?permissao ?username ?repositorio_uri WHERE {{
        ?s foaf:mbox "{email}" ;
           :password "{password}" ;  # Corrigido para :password
           :temPermissao ?permissao ;
           :repo ?repositorio_uri ;
           :username ?username .
        # Filtrar pelo nome do repositório se a URI do repo for um literal com o nome
        # ou se for uma URI que contenha o nome. Ajustar conforme a modelagem.
        # Esta forma assume que ?repositorio_uri é um literal ou uma URI que queremos comparar com repo_name_param
        FILTER(CONTAINS(LCASE(STR(?repositorio_uri)), LCASE("{repo_name_param}")))
    }}
    LIMIT 1
    """
    # print(f"DEBUG: Query Login SPARQL: {query}") # Para depuração
    results = execute_sparql_query(query)

    if not results or not results.get('results', {}).get('bindings'):
        return jsonify({'message': 'Usuário ou senha inválidos para esse repositório'}), 401

    user_data = results['results']['bindings'][0]
    user_uri = user_data['s']['value']
    user_permission = user_data['permissao']['value']
    user_name = user_data['username']['value']
    # repo_uri_from_user_db é a URI/literal do repositório associado ao usuário no BD de usuários
    repo_uri_from_user_db = user_data['repositorio_uri']['value']

    # Obter detalhes do repositório usando o nome fornecido (repo_name_param)
    # A função obter_repositorio_por_nome deve buscar no local correto dos metadados dos repositórios.
    repo_details = obter_repositorio_por_nome(repo_name_param)
    if not repo_details:
        return jsonify({'message': f"Detalhes do repositório '{repo_name_param}' não encontrados."}), 404


    token = str(uuid.uuid4())
    validade = datetime.now() + timedelta(hours=24) # Token válido por 24 horas

    update_query = f"""
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    DELETE {{ <{user_uri}> :token ?old_token ; :validade ?old_validade . }}
    INSERT {{ <{user_uri}> :token "{token}" ; :validade "{validade.isoformat()}Z" . }} # Adicionado Z para UTC
    WHERE {{
        OPTIONAL {{ <{user_uri}> :token ?old_token . }}
        OPTIONAL {{ <{user_uri}> :validade ?old_validade . }}
    }}
    """
    # print(f"DEBUG: Query Update Token SPARQL: {update_query}") # Para depuração
    response = execute_sparql_update(update_query)

    if response.status_code != 200: # Geralmente Fuseki retorna 200 para updates bem sucedidos (ou 204 No Content)
        # Logar o erro response.text
        print(f"Erro ao atualizar token: {response.status_code} - {response.text}")
        return jsonify({'message': 'Falha ao atualizar token e validade'}), 500

    return jsonify({
        'message': 'Login successful',
        'user': user_name,
        'email': email,
        'permissao': user_permission,
        'token': token,
        'repositorio': repo_uri_from_user_db, # URI/literal do repo associado ao usuário
        'validade': validade.isoformat() + "Z", # ISO 8601 com Z para UTC
        'repositorio_conectado': repo_details # Detalhes do repositório obtidos por obter_repositorio_por_nome
    }), 200

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
    repo_name = data.get('repo_name') # Nome do repositório para associação

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
    # check_results = execute_sparql_query(check_query)
    # if check_results.get('boolean', False):
    #     return jsonify({'message': f"Usuário com username '{username}' já existe."}), 409

    user_resource_uri = f":{username}" # Usando o username como parte da URI local

    # Query para inserir novo usuário, usando :password e incluindo email e repo_name
    insert_query = f"""
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    INSERT DATA {{
        {user_resource_uri} rdf:type :Curador ;
                   :username "{username}" ;
                   :password "{password}" ; # Usando :password conforme TTL
                   :temPermissao "{permissao}" ;
                   foaf:mbox "{email}" ;
                   :repo "{repo_name}" . # Armazenando o nome do repositório como literal
    }}
    """
    # print(f"DEBUG: Query Insert Usuário SPARQL: {insert_query}") # Para depuração
    response = execute_sparql_update(insert_query)

    if response.status_code == 200: # Ou 204, dependendo da configuração do Fuseki
        base_uri = FUSEKI_QUERY_URL.split('/usuarios/query')[0] + "/usuarios#" # Tenta inferir a base URI
        full_user_uri = base_uri + username
        return jsonify({'message': 'Usuário adicionado com sucesso.', 'user_uri': full_user_uri}), 201
    else:
        # Logar o erro response.text
        print(f"Erro ao adicionar usuário: {response.status_code} - {response.text}")
        return jsonify({'message': 'Falha ao adicionar usuário.'}), 500

