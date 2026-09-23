from flask import Blueprint, request, jsonify
import requests
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
from werkzeug.security import generate_password_hash, check_password_hash
from ..blueprints.repositorios import obter_repositorio_por_nome
from ..blueprints.auth import token_required
from ..consultas import slugificar
from ..config_loader import load_config
acessoapp = Blueprint('acessoapp', __name__)




config = load_config()

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
    response = requests.get(FUSEKI_QUERY_URL, params={
                            'query': query}, headers=headers)
    return response.json()


def extrair_repositorio(url):

    ultimo_barra_index = url.rfind('/')
    if ultimo_barra_index != -1:
        return url[ultimo_barra_index + 1:]
    else:
        # Se não houver '/', retorne a própria URL
        return url


def sparql_escape(value):
    return (str(value)
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r'))

@acessoapp.route('/login', methods=['POST'])
def login():

    data = request.json
    email = data.get('email')
    password = data.get('password')
    repo = data.get('repository')
    name = data.get('name')

    try:
        query = f"""
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        prefix :      <https://guara.ueg.br/fuseki/usuarios#>
        SELECT ?s ?permissao ?username ?repositorio ?senha WHERE {{
            ?s foaf:mbox "{sparql_escape(email)}" ;
               foaf:password ?senha .
               ?s :temPermissao ?permissao.
               ?s :repo ?repositorio.
               ?s :username ?username
               FILTER(CONTAINS(LCASE(STR(?repositorio)), "{ sparql_escape(str.lower(name)) }"))
        }}
        """

        results = execute_sparql_query(query)
        if not results['results']['bindings']:
            return jsonify({'message': 'Usuário ou senha inválidos para esse repositório'}), 401

        user_data = results['results']['bindings'][0]
        stored_hash = user_data['senha']['value']

        if not check_password_hash(stored_hash, password):
            return jsonify({'message': 'Usuário ou senha inválidos para esse repositório'}), 401

        user_uri = user_data['s']['value']
        user_permission = user_data['permissao']['value']
        user_name = user_data['username']['value']
        repo = user_data['repositorio']['value']

        #buscar repositório
        print('name', name)
        repo_response = obter_repositorio_por_nome(name)

        print(repo_response)

        # Gerar token de autenticação
        token = str(uuid.uuid4())
        validade = datetime.now() + timedelta(hours=24)  # Token válido por 24 horas

        # Atualizar RDF com token e validade
        update = f"""
        PREFIX : <https://guara.ueg.br/fuseki/usuarios#>
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
            'repositorio_conectado': repo_response  # Adicionando os repositórios
        }), 200

    except Exception as e:
        print('Erro no login:', e)
        return jsonify({'message': 'Erro interno ao processar o login'}), 500


@acessoapp.route('/add_user', methods=['POST'])
@token_required
def add_curador():
    data = request.json
    required_fields = ['username', 'password', 'permissao', 'email', 'repo']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f"Campo '{field}' é obrigatório"}), 400

    username = data.get('username')
    password = data.get('password')
    permissao = data.get('permissao')
    email = data.get('email')
    repo = data.get('repo')

    # 'repo' pode vir como string única ("festas_populares") ou lista
    # (["festas_populares", "diocese"]) - vira a mesma string separada
    # por vírgula que o login já espera em :repo.
    if isinstance(repo, list):
        repo = ','.join(repo)

    # username vira o segmento de URI local (:{username_uri}) sem aspas -
    # precisa ser um slug seguro (nem todo caractere válido num username
    # digitado pelo usuário é válido ali, ex.: "@" quebra a query, sendo
    # interpretado como início de LANGTAG). O texto original continua
    # gravado tal como digitado no campo :username (entre aspas).
    username_uri = slugificar(username)
    password_hash = generate_password_hash(password)

    update = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX : <https://guara.ueg.br/fuseki/usuarios#>
    INSERT DATA {{
        :{username_uri} rdf:type :Curador ;
                   :username "{sparql_escape(username)}" ;
                   foaf:mbox "{sparql_escape(email)}" ;
                   foaf:password "{sparql_escape(password_hash)}" ;
                   :repo "{sparql_escape(repo)}" ;
                   :temPermissao "{sparql_escape(permissao)}" .
    }}
    """
    response = execute_sparql_update(update)
    if response.status_code == 200:
        return jsonify({'message': 'Curador added successfully'}), 201
    else:
        return jsonify({'message': 'Failed to add curador', 'detalhe': response.text}), 500
