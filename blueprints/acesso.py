from flask import Blueprint, request, jsonify
import requests
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
from blueprints.repositorios import obter_repositorio_por_nome

acessoapp = Blueprint('acessoapp', __name__)

def load_config(filename):
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
    return response.json()

def extrair_repositorio(url):
    ultimo_barra_index = url.rfind('/')
    return url[ultimo_barra_index + 1:] if ultimo_barra_index != -1 else url

@acessoapp.route('/login', methods=['POST'])
def login():
   """
    Realiza o login do usuário no repositório solicitado.
    ---
    tags:
      - Autenticação
    parameters:
      - in: body
        name: body
        required: true
        description: Dados de autenticação
        schema:
          type: object
          required:
            - email
            - password
            - name
            - repository
          properties:
            email:
              type: string
              example: usuario@dominio.com
            password:
              type: string
              example: senha123
            repository:
              type: string
              example: repositorio-1
            name:
              type: string
              example: repositorio-1
    responses:
      200:
        description: Login realizado com sucesso
        schema:
          type: object
          properties:
            message:
              type: string
            user:
              type: string
            email:
              type: string
            permissao:
              type: string
            token:
              type: string
            repositorio:
              type: string
            validade:
              type: string
            repositorio_conectado:
              type: object
      401:
        description: Usuário ou senha inválidos
      500:
        description: Erro ao atualizar token e validade
    """
    data = request.json
    email = data.get('email')
    password = data.get('password')
    repo = data.get('repository')
    name = data.get('name')

    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#> 
    SELECT ?s ?permissao ?username ?repositorio WHERE {{
        ?s foaf:mbox "{email}" ;
           foaf:password "{password}" .
        ?s :temPermissao ?permissao.
        ?s :repo ?repositorio.
        ?s :username ?username
        FILTER(CONTAINS(LCASE(STR(?repositorio)), "{str.lower(name)}"))
    }}
    """

    results = execute_sparql_query(query)

    if not results['results']['bindings']:
        return jsonify({'message': 'Usuário ou senha inválidos para esse repositório'}), 401

    user_data = results['results']['bindings'][0]
    user_uri = user_data['s']['value']
    user_permission = user_data['permissao']['value']
    user_name = user_data['username']['value']
    repo = user_data['repositorio']['value']

    repo_response = obter_repositorio_por_nome(name)

    token = str(uuid.uuid4())
    validade = datetime.now() + timedelta(hours=24)

    update = f"""
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    DELETE {{ <{user_uri}> :token ?old_token ; :validade ?old_validade }}
    INSERT {{ <{user_uri}> :token "{token}" ; :validade "{validade.isoformat()}"}}
    WHERE {{
        OPTIONAL {{ <{user_uri}> :token ?old_token }}
        OPTIONAL {{ <{user_uri}> :validade ?old_validade }}
    }}
    """

    response = execute_sparql_update(update)
    if response.status_code != 200:
        return jsonify({'message': 'Failed to update token and validade'}), 500

    return jsonify({
        'message': 'Login successful',
        'user': user_name,
        'email': email,
        'permissao': user_permission,
        'token': token,
        'repositorio': repo,
        'validade': validade.isoformat(),
        'repositorio_conectado': repo_response
    }), 200

@acessoapp.route('/add_user', methods=['POST'])
def add_curador():
    """
    Adiciona um novo curador ao sistema.
    ---
    tags:
      - Usuários
    parameters:
      - in: body
        name: body
        required: true
        description: Dados do curador a ser adicionado
        schema:
          type: object
          required:
            - username
            - password
            - permissao
          properties:
            username:
              type: string
              example: curador123
            password:
              type: string
              example: senhaSegura
            permissao:
              type: string
              example: leitura_escrita
    responses:
      201:
        description: Curador adicionado com sucesso
        schema:
          type: object
          properties:
            message:
              type: string
              example: Curador added successfully
      500:
        description: Erro ao adicionar curador
        schema:
          type: object
          properties:
            message:
              type: string
              example: Failed to add curador
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')
    permissao = data.get('permissao')

    update = f"""
    PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
    INSERT DATA {{
        :{username} rdf:type :Curador ;
                   :username "{username}" ;
                   :password "{password}" ;
                   :temPermissao "{permissao}" .
    }}
    """
    response = execute_sparql_update(update)
    if response.status_code == 200:
        return jsonify({'message': 'Curador added successfully'}), 201
    else:
        return jsonify({'message': 'Failed to add curador'}), 500

