import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import requests
from ..consultas import get_sparq_repo, get_prefix, slugificar
from ..config_loader import load_config
from urllib.parse import urlencode
from ..blueprints.auth import token_required
from ..fuseki_utils import resolve_fuseki_endpoint
from .sparql_escape import escapar_literal_sparql

repo_app = Blueprint('repo_app', __name__)
NAMESPACE_REPO = "https://guara.ueg.br/fuseki"


def criar_dataset_fuseki(nome_dataset, tipo_dataset='tdb2'):
    """Cria um dataset novo no Fuseki via API administrativa. Usa
    FUSEKI_ADMIN_USER/FUSEKI_ADMIN_PASSWORD (credenciais de admin do
    Fuseki, nunca hardcoded aqui) e o mesmo FUSEKI_BASE_URL usado para
    as demais conexões."""
    fuseki_admin_url = os.getenv('FUSEKI_BASE_URL', 'http://localhost:3030') + '/$/datasets'
    admin_user = os.getenv('FUSEKI_ADMIN_USER')
    admin_password = os.getenv('FUSEKI_ADMIN_PASSWORD')
    return requests.post(
        fuseki_admin_url,
        data={'dbName': nome_dataset, 'dbType': tipo_dataset},
        auth=(admin_user, admin_password)
    )


def seed_classe_acervo(uri_valor):
    """Cria a classe raiz 'Acervo' no dataset recém-criado de um
    repositório - sem ela, /classapi/adicionar_classe fica travado (exige
    'subclassof', ou seja, sempre precisa de uma classe-mãe já existente)
    e /fis/create também (exige 'colecao' apontando pra uma classe)."""
    sparqapi_url = resolve_fuseki_endpoint(uri_valor) + '/' + load_config().get('update')
    sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX : <{uri_valor}#>
        INSERT DATA {{
            :Acervo rdf:type owl:Class ;
                    rdfs:label "Acervo" ;
                    rdfs:comment "Classe geral para o acervo" .
        }}
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    response = requests.post(sparqapi_url, headers=headers, data=urlencode({'update': sparql_query}))
    response.raise_for_status()
    return response


def remover_registro_repositorio(repo_uri):
    """Reverte o INSERT do registro do repositório em repositoriosamigos -
    usado quando um passo posterior (criar o dataset) falha, pra não
    deixar um repositório 'fantasma' listado sem dataset por trás."""
    sparqapi_url = load_config().get('repo_update_url')
    sparql_query = f"DELETE WHERE {{ <{repo_uri}> ?p ?o }}"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    try:
        requests.post(sparqapi_url, headers=headers, data=urlencode({'update': sparql_query}))
    except requests.exceptions.RequestException:
        pass


def obter_repositorio_por_nome(name):
    response = list()  # Chama a função
    if response.status_code != 200:   # Verifica erro na resposta
        return None
   
    repositorios = response.get_json()  # Extrai o JSON corretamente

    

    # Garante que está iterando sobre uma lista válida
    if "results" in repositorios and "bindings" in repositorios["results"]:
        for repo in repositorios["results"]["bindings"]:
            print(repo["nome"]["value"].lower(),' =? ',name.lower())
            if repo["nome"]["value"].lower() == name.lower():
                return {
                    "nome": repo["nome"]["value"],
                    "uri": repo["uri"]["value"],
                    "contato": repo["contato"]["value"],
                    "descricao": repo["descricao"]["value"],
                    "responsavel": repo["responsavel"]["value"]
                }
    
    return None  # Se não encontrar o repositórioreturn None 

@repo_app.route('/list', methods=['GET','POST'])
@repo_app.route('/listar_repositorios', methods=['GET','POST'])
def list():
    try:
        nome = request.args.get('name', default=None, type=str)
        filtro = f'FILTER(?nome = "{nome}"^^xsd:string)' if nome else ''
        sparqapi_url =  load_config().get('repo_query_url')
        #print('url:',sparqapi_url)
        sparql_query = get_sparq_repo().replace("%filter%", filtro)
                        
        #print('query:',sparql_query)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            result = response.json()
            return jsonify(result)
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except TypeError as e:
        return jsonify({"error": "TypeError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/create', methods=['POST'])
@token_required
def create():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['uri', 'nome', 'contato', 'descricao', 'responsavel']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        slug = slugificar(data['uri'])
        uri_valor = f"{NAMESPACE_REPO}/{slug}"
        repo_uri = f"{NAMESPACE_REPO}/repositorios/{slug}"
        sparqapi_url = load_config().get('repo_update_url')

        nome = escapar_literal_sparql(data['nome'])
        contato = escapar_literal_sparql(data['contato'])
        descricao = escapar_literal_sparql(data['descricao'])
        responsavel = escapar_literal_sparql(data['responsavel'])

        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            PREFIX rpa:  <{NAMESPACE_REPO}/repositorios#>
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            INSERT DATA {{
                <{repo_uri}> rdf:type rpa:Repositorio ;
                                rpa:uri "{uri_valor}" ;
                                rpa:nome "{nome}" ;
                                rpa:contato "{contato}" ;
                                rpa:descricao "{descricao}" ;
                                rpa:responsavel "{responsavel}" .
            }}
        """

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code != 200:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        # Passo 2: criar o dataset de verdade no Fuseki para o conteúdo
        # deste repositório (o passo 1 só cadastra o nome/descrição).
        dataset_response = criar_dataset_fuseki(slug)
        if dataset_response.status_code not in (200, 201):
            remover_registro_repositorio(repo_uri)
            return jsonify({
                "error": "DatasetCreationFailed",
                "message": f"Repositório não criado: falha ao criar o dataset no Fuseki "
                           f"({dataset_response.status_code}): {dataset_response.text}"
            }), 502

        # Passo 3: semear a classe raiz "Acervo" - sem ela não dá pra
        # criar nenhuma outra classe nem objeto físico nesse repositório.
        try:
            seed_classe_acervo(uri_valor)
        except requests.exceptions.RequestException as e:
            return jsonify({
                "message": "Repositório e dataset criados, mas falhou ao criar a classe "
                           "'Acervo' - crie manualmente antes de adicionar conteúdo.",
                "aviso": str(e),
                "uri": uri_valor,
                "slug": slug
            }), 200

        return jsonify({"message": "Repositório criado com sucesso", "uri": uri_valor, "slug": slug}), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except ValueError as e:
        return jsonify({"error": "ValueError", "message": str(e)}), 400

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/upload_avatar', methods=['POST'])
@token_required
def upload_avatar():
    try:
        slug_bruto = request.form.get('uri')
        arquivo = request.files.get('avatar')

        if not slug_bruto:
            return jsonify({"error": "Invalid input", "message": "Expected form field 'uri'"}), 400
        if not arquivo or not arquivo.filename:
            return jsonify({"error": "Invalid input", "message": "Expected file field 'avatar'"}), 400

        slug = slugificar(slug_bruto)
        extensao = os.path.splitext(arquivo.filename)[1].lower().lstrip('.')
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
        if extensao not in allowed_extensions:
            return jsonify({
                "error": "Invalid input",
                "message": f'Extensão "{extensao}" não permitida',
                "extensoes_permitidas": sorted(allowed_extensions)
            }), 400

        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        repo_folder = os.path.join(upload_folder, slug)
        os.makedirs(repo_folder, exist_ok=True)

        nome_arquivo = secure_filename(f"avatar.{extensao}")
        arquivo.save(os.path.join(repo_folder, nome_arquivo))

        avatar_path = f"/uploadapi/midias/{slug}/{nome_arquivo}"
        uri_valor = f"{NAMESPACE_REPO}/{slug}"

        sparqapi_url = load_config().get('repo_update_url')
        sparql_update = f"""
            PREFIX rpa: <{NAMESPACE_REPO}/repositorios#>
            DELETE {{ ?repo rpa:avatar ?old }}
            INSERT {{ ?repo rpa:avatar "{escapar_literal_sparql(avatar_path)}" }}
            WHERE {{
                ?repo rpa:uri "{escapar_literal_sparql(uri_valor)}" .
                OPTIONAL {{ ?repo rpa:avatar ?old }}
            }}
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        response = requests.post(sparqapi_url, headers=headers, data=urlencode({'update': sparql_update}))

        if response.status_code != 200:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        return jsonify({"message": "Avatar atualizado com sucesso", "avatar": avatar_path}), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/create_dataset', methods=['POST'])
@token_required
def criar_dataset():
    try:
        data = request.get_json()

        required_fields = ['nome']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        nome_dataset = data['nome']
        tipo_dataset = data.get('tipo', 'tdb2')

        response = criar_dataset_fuseki(nome_dataset, tipo_dataset)

        if response.status_code == 200:
            return jsonify({"message": "Dataset criado com sucesso", "nome": nome_dataset}), 200
        else:
            return jsonify({
                "error": response.status_code,
                "message": response.text
            }), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500