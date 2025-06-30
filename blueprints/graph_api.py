from flask import Blueprint, jsonify, current_app
from utils import execute_sparql_query
from config_loader import load_config
from consultas import get_sparq_repo, get_sparq_all
import requests

# Cria um novo blueprint para a API do gráfico
graph_api_app = Blueprint('graph_api_app', __name__)

# Carrega a configuração principal
config = load_config('config.json')


@graph_api_app.route('/main_data', methods=['GET'])
def get_main_graph_data():
    """
    Este endpoint único busca todos os dados necessários para renderizar o gráfico principal.
    1. Busca a lista completa de repositórios de metadados.
    2. Itera sobre cada repositório encontrado e tenta buscar os objetos de dados.
    3. Ignora os repositórios que falharem (ex: offline ou URI incorreta) e continua tentando com os próximos.
    4. Retorna os dados do primeiro repositório que responder com sucesso.
    """
    try:
        # Etapa 1: Buscar a lista de todos os repositórios de metadados
        repo_query_url = config.get('repo_query_url')
        if not repo_query_url:
            raise Exception("A URL de consulta de repositórios (repo_query_url) não está configurada.", 500)

        repos_query = get_sparq_repo().replace("%filter_aqui%", "")
        repos_result = execute_sparql_query(repo_query_url, repos_query)

        collections_bindings = repos_result.get('results', {}).get('bindings', [])
        if not collections_bindings:
            return jsonify({"error": "Nenhum repositório de dados foi encontrado no dataset de metadados."}), 404

        # Etapa 2: Iterar sobre os repositórios e tentar buscar os objetos de cada um
        for repo_binding in collections_bindings:
            # Validação para garantir que o campo 'uri' existe antes de acessá-lo
            if 'uri' not in repo_binding or 'value' not in repo_binding['uri']:
                current_app.logger.warning(f"Repositório ignorado por não ter uma 'uri' válida: {repo_binding}")
                continue  # Pula para o próximo repositório

            repo_data_uri = repo_binding['uri']['value']

            # Garante que a URI do repositório de dados seja um endpoint de consulta válido
            data_endpoint_uri = repo_data_uri
            if not data_endpoint_uri.endswith(('/query', '/sparql')):
                data_endpoint_uri = f"{data_endpoint_uri.rstrip('/')}/query"

            try:
                current_app.logger.info(f"Tentando buscar objetos do acervo em: {data_endpoint_uri}")

                # Prepara e executa a query para buscar todos os objetos do acervo
                repo_base_uri_inferred = data_endpoint_uri.rsplit('/', 1)[0] + "#"
                objects_query = f"PREFIX : <{repo_base_uri_inferred}> " + get_sparq_all().replace('%keyword%',
                                                                                                  '').replace('%tipo%',
                                                                                                              '')

                objects_result = execute_sparql_query(data_endpoint_uri, objects_query)
                objects_bindings = objects_result.get('results', {}).get('bindings', [])

                # Se a consulta for bem-sucedida, monta a resposta final e a retorna
                final_data = {
                    "collections": collections_bindings,  # Retorna a lista completa de todos os repositórios
                    "objects": objects_bindings,  # Retorna os objetos do primeiro repositório que funcionou
                    "loaded_from": data_endpoint_uri  # Informação de depuração
                }

                current_app.logger.info(f"Dados carregados com sucesso do repositório: {data_endpoint_uri}")
                return jsonify(final_data)

            except requests.exceptions.HTTPError as http_err:
                current_app.logger.warning(
                    f"Falha ao consultar o repositório {data_endpoint_uri}: {http_err}. Tentando o próximo.")
                continue  # Se der erro (ex: 404), ignora e tenta o próximo repositório
            except Exception as e:
                current_app.logger.warning(
                    f"Erro inesperado ao consultar {data_endpoint_uri}: {e}. Tentando o próximo.")
                continue  # Outros erros, como timeout

        # Se o loop terminar sem sucesso em nenhum repositório
        return jsonify({"error": "Não foi possível carregar os dados de nenhum dos repositórios configurados."}), 404

    except Exception as e:
        error_message = str(e.args[0]) if e.args else str(e)
        status_code = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], int) else 500

        current_app.logger.error(f"Erro crítico em get_main_graph_data: {e}")
        return jsonify({"error": "Erro Interno do Servidor", "message": error_message}), status_code

