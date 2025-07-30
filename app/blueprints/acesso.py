from flask import Blueprint, request, jsonify
import requests
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
from ..blueprints.repositorios import obter_repositorio_por_nome
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

@acessoapp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    repo = data.get('repository')
    name=data.get('name')
    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    prefix :      <http://guara.ueg.br/ontologias/usuarios#> 
    SELECT ?s ?permissao ?username ?repositorio WHERE {{
        ?s foaf:mbox "{email}" ;
           foaf:password "{password}" .
           ?s :temPermissao ?permissao.
           ?s :repo ?repositorio.
           ?s :username ?username
           FILTER(CONTAINS(LCASE(STR(?repositorio)), "{  str.lower(name) }"))
    }}
    """
    #print('repo:',repo)
    print('query',query)
    results = execute_sparql_query(query)
    #print('result:',results)



    
    if not results['results']['bindings']:
        return jsonify({'message': 'Usuário ou senha inválidos para esse repositório'}), 401
    
    

    user_data = results['results']['bindings'][0]
    user_uri = user_data['s']['value']
    user_permission = user_data['permissao']['value']
    user_name = user_data['username']['value']
    repo = user_data['repositorio']['value']

    #buscar repositório
    print('name',name)
    repo_response = obter_repositorio_por_nome(name)
    
    print(repo_response)
    
    # Gerar token de autenticação
    token = str(uuid.uuid4())
    validade = datetime.now() + timedelta(hours=24)  # Token válido por 24 horas

    # Atualizar RDF com token e validade
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
        'repositorio_conectado': repo_response  # Adicionando os repositórios
    }), 200


@acessoapp.route('/add_user', methods=['POST'])
def add_curador():
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
