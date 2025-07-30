from flask import Blueprint, request, jsonify
import requests
from ..consultas import get_sparq_repo, get_prefix
from ..config_loader import load_config
from urllib.parse import urlencode
from ..config_loader import load_config

repo_app = Blueprint('repo_app', __name__)


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
        sparqapi_url = load_config().get('repo_query_url')
        #print('url:',sparqapi_url)
        sparql_query = get_sparq_repo().replace("%filter%", filtro)
                        
        print('query:',sparql_query)
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
def create():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['uri', 'nome','contato','descricao','responsavel']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        

        prefix_base = load_config().get('prefix_base_repo')
        repo_uri=prefix_base+data['uri']
        sparqapi_url = load_config().get('class_update_url')
        
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            prefix :      <{repo_uri}#> 
            prefix rpa:   <http://200.137.241.247:8080/fuseki/repositorios#> 
            prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
            prefix owl:   <http://www.w3.org/2002/07/owl#> 
            prefix xsd:   <http://www.w3.org/2001/XMLSchema#> 
            prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
            
            INSERT DATA {{
                <{repo_uri}> rdf:type owl:Class ;
                                rpa:uri "{data['uri']}" ;
                                rpa:nome "{data['nome']}" ;
                                rpa:contato "{data['contato']}" ;
                                rpa:descricao "{data['descricao']}" ;
                                rpa:responsavel "{data['responsavel']}" .
            }}
        """
        #print('uri', repo_uri)
        #print('q', sparql_query)

        # Preparação dos headers e dados para a requisição POST
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

        if response.status_code == 200:
            return jsonify({"message": "Classe adicionada com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/create_dataset', methods=['POST'])
def criar_dataset():
    try:
        data = request.get_json()
        
        required_fields = ['nome']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        nome_dataset = data['nome']
        tipo_dataset = data.get('tipo', 'tdb2') 

        # URL do Fuseki
        fuseki_admin_url = 'http://localhost:3030/$/datasets'  # ou IP externo

        # Autenticação (se necessário)
        username = 'admin'
        password = '@adm1n'

        # Dados do formulário
        form_data = {
            'dbName': nome_dataset,
            'dbType': tipo_dataset
        }

        # Enviar requisição
        response = requests.post(
            fuseki_admin_url,
            data=form_data,
            auth=(username, password)
        )

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