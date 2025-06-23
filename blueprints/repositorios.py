from flask import Blueprint, request, jsonify, current_app, g # Importado 'g' para acessar user_uri
# Importar as funções refatoradas de utils.py
from utils import execute_sparql_query, execute_sparql_update
from consultas import get_sparq_repo
from config_loader import load_config
from urllib.parse import urlencode # Ainda necessário para form_payload em criar_dataset_fuseki
from blueprints.auth import token_required # Importar o decorador de token

repo_app = Blueprint('repo_app', __name__)

# Carregar a configuração globalmente para o módulo
config = load_config('config.json')
FUSEKI_URL = config.get('fuseki_url')
REPO_QUERY_URL = config.get('repo_query_url')
REPO_UPDATE_URL = config.get('repo_update_url')
USER_QUERY_URL = config.get('user_query_url') # Necessário para buscar repositórios do usuário

# Função auxiliar, não é um endpoint HTTP
def obter_repositorio_por_nome(name):
    """
    Obtém os detalhes de um repositório específico pelo seu nome.
    Esta função agora realiza a consulta SPARQL diretamente.
    """
    try:
        if not REPO_QUERY_URL:
            current_app.logger.error("Configuração 'repo_query_url' não encontrada para obter_repositorio_por_nome.")
            return None

        # Vamos construir o filtro aqui para maior clareza:
        filtro_sparql = ''
        if name:
            nome_escaped = name.replace('"', '\\"')
            # Ajustado para usar o placeholder %keyword% em get_sparq_repo
            filtro_sparql = f'FILTER(LCASE(STR(?nome)) = LCASE("{nome_escaped}"))'

        sparql_query_template = get_sparq_repo()
        # Assume que get_sparq_repo() tem um placeholder para o filtro.
        # Se não tiver, você precisará modificar get_sparq_repo() ou injetar o filtro de outra forma.
        sparql_query = sparql_query_template.replace("%filter_aqui%", filtro_sparql) # Usar um placeholder distinto

        current_app.logger.debug(f"SPARQL query para obter_repositorio_por_nome: {sparql_query}")

        # Usando execute_sparql_query de utils.py
        results = execute_sparql_query(REPO_QUERY_URL, sparql_query)

        if "results" in results and "bindings" in results["results"]:
            for repo_binding in results["results"]["bindings"]:
                if repo_binding.get("nome", {}).get("value", "").lower() == name.lower():
                    return {
                        "nome": repo_binding.get("nome", {}).get("value"),
                        "uri": repo_binding.get("uri", {}).get("value"),
                        "contato": repo_binding.get("contato", {}).get("value"),
                        "descricao": repo_binding.get("descricao", {}).get("value"),
                        "responsavel": repo_binding.get("responsavel", {}).get("value")
                    }
    except Exception as e:
        current_app.logger.error(f"Erro ao obter repositório por nome: {str(e)}")
    return None

@repo_app.route('/listar_repositorios', methods=['GET'])
def listar_repositorios_endpoint():
    """
    Lista os repositórios de metadados disponíveis.
    Pode-se filtrar por um nome específico de repositório.
    ---
    tags:
      - Repositórios
    parameters:
      - name: name
        in: query
        required: false
        description: Nome exato (case-insensitive) do repositório a ser filtrado. Se omitido, lista todos.
        schema:
          type: string
        example: "Meu Repositório Principal"
    responses:
      200:
        description: Lista de repositórios retornada com sucesso.
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
                      example: ["nome", "uri", "contato", "descricao", "responsavel"]
                results:
                  type: object
                  properties:
                    bindings:
                      type: array
                      items:
                        type: object
                        properties:
                          # CORREÇÃO AQUI: Removendo o 'type: object' aninhado desnecessariamente e a chave '}}}' extra.
                          # E garantindo a sintaxe YAML correta para dicionários e aninhamento.
                          uri:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "uri"
                              value:
                                type: string
                                format: uri
                                example: "http://example.org/repo/Repo1"
                          nome:
                            type: object
                            properties:
                              type:
                                type: string
                                example: "literal"
                              value:
                                type: string
                                example: "Repositório 1"
      400:
        description: Erro na requisição (ex falha ao carregar configuração).
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string"}
                message: {"type": "string"}
      500:
        description: Erro interno no servidor ou falha na comunicação SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string"}
                message: {"type": "string"}
    """
    try:
        nome_filtro = request.args.get('name', default=None, type=str)

        if not REPO_QUERY_URL:
            current_app.logger.error("Configuração 'repo_query_url' não encontrada para listar_repositorios_endpoint.")
            return jsonify({"error": "Configuration Error", "message": "Endpoint de query de repositório não configurado."}), 500

        filtro_sparql = ''
        if nome_filtro:
            nome_escaped = nome_filtro.replace('"', '\\"')
            filtro_sparql = f'FILTER(LCASE(STR(?nome)) = LCASE("{nome_escaped}"))'

        sparql_query_template = get_sparq_repo()
        sparql_query = sparql_query_template.replace("%filter_aqui%", filtro_sparql)

        current_app.logger.debug(f"SPARQL query para listar repositórios: {sparql_query}")

        result = execute_sparql_query(REPO_QUERY_URL, sparql_query)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Erro em listar_repositorios_endpoint: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Query Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@repo_app.route('/adicionar_repo', methods=['POST'])
def adicionar_repo_endpoint():
    """
    Adiciona uma nova definição de repositório ao grafo de metadados.
    Esta operação cria um recurso :RepoID rdf:type owl:Class com as propriedades fornecidas.
    ---
    tags:
      - Repositórios
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - id_local_repo
              - nome
              - contato
              - descricao
              - responsavel
            properties:
              id_local_repo:
                type: string
                description: Identificador local único para o repositório (ex 'meu_repo_principal'). Será usado para formar a URI completa.
                example: "meu_repo_principal"
              nome:
                type: string
                description: Nome legível do repositório.
                example: "Repositório de Fotografias Históricas da Cidade"
              contato:
                type: string
                format: email
                description: Informação de contato para o repositório.
                example: "contato@fotohistorica.org"
              descricao:
                type: string
                description: Breve descrição do conteúdo e propósito do repositório.
                example: "Acervo digitalizado de fotografias da cidade de Anápolis de 1900 a 1950."
              responsavel:
                type: string
                description: Nome da instituição ou pessoa responsável pelo repositório.
                example: "Arquivo Histórico Municipal de Anápolis"
    responses:
      201:
        description: Repositório (como classe) adicionado com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Definição de repositório adicionada com sucesso."
                repositorio_uri:
                  type: string
                  format: uri
                  example: "http://guara.ueg.br/ontologias/v1/repositoriosamigos#meu_repo_principal"
                id_local_repo:
                  type: string
                  example: "meu_repo_principal"
      400:
        description: Dados de entrada inválidos ou campos obrigatórios ausentes.
      500:
        description: Erro interno no servidor ou falha na atualização SPARQL.
    """
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

        required_fields = ['id_local_repo', 'nome','contato','descricao','responsavel']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório e não pode ser vazio."}), 400

        prefix_base_repo_config = config.get('prefix_base_repo')
        sparql_update_url = REPO_UPDATE_URL

        if not prefix_base_repo_config or not sparql_update_url:
            current_app.logger.error("Configurações 'prefix_base_repo' ou 'repo_update_url' não encontradas.")
            return jsonify({"error": "Configuration Error", "message": "Configuração do servidor incompleta."}), 500

        if not prefix_base_repo_config.endswith(('#', '/')):
            prefix_base_repo_config += "#"

        id_local = data['id_local_repo'].replace(" ", "_")
        repo_uri_completa = f"<{prefix_base_repo_config}{id_local}>"

        sparql_update = f"""
            PREFIX rpa:   <http://guara.ueg.br/ontologias/v1/repositorios#>
            PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl:   <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

            INSERT DATA {{
                {repo_uri_completa} rdf:type owl:NamedIndividual ;
                                    rdf:type rpa:Repositorio ;
                                    rpa:idLocal "{id_local}" ;
                                    rpa:nome "{data['nome'].replace('"', '\\"')}" ;
                                    rpa:contato "{data['contato'].replace('"', '\\"')}" ;
                                    rpa:descricao \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\" ;
                                    rpa:responsavel "{data['responsavel'].replace('"', '\\"')}" .
            }}
        """
        current_app.logger.debug(f"SPARQL update para adicionar repositório: {sparql_update}")

        execute_sparql_update(sparql_update_url, sparql_update)

        return jsonify({
            "message": "Definição de repositório adicionada com sucesso.",
            "repositorio_uri": repo_uri_completa.strip("<>"),
            "id_local_repo": id_local
            }), 201

    except Exception as e:
        current_app.logger.error(f"Erro em adicionar_repo_endpoint: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Failed", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@repo_app.route('/create_dataset', methods=['POST'])
def criar_dataset_fuseki():
    """
    Cria um novo dataset (TDB2 por padrão) no servidor Apache Fuseki.
    Este endpoint interage diretamente com a API de administração do Fuseki.
    Requer credenciais de administrador do Fuseki configuradas no servidor da API.
    ---
    tags:
      - Repositórios
      - Administração Fuseki
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - nome_dataset
            properties:
              nome_dataset:
                type: string
                description: Nome para o novo dataset a ser criado no Fuseki (ex 'meu_novo_acervo').
                example: "acervo_fotografico_regional"
              tipo_dataset: # dbType no Fuseki
                type: string
                description: Tipo de armazenamento do dataset. Padrão é 'tdb2'. Outras opções podem ser 'mem'.
                default: "tdb2"
                enum: ["tdb2", "mem"]
                example: "tdb2"
              fuseki_admin_url:
                type: string
                format: uri
                description: "(Opcional no request, pego da config) URL base do admin do Fuseki (ex http://localhost:3030)."
                example: "http://localhost:3030"
              fuseki_admin_user:
                type: string
                description: "(Opcional no request, pego da config) Usuário admin do Fuseki."
                example: "admin"
              fuseki_admin_password:
                type: string
                format: password
                description: "(Opcional no request, pego da config) Senha do admin do Fuseki."
                example: "senhaSuperSecreta"

    responses:
      200: # Fuseki retorna 200 OK para criação bem-sucedida
        description: Dataset criado com sucesso no Fuseki.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Dataset 'acervo_fotografico_regional' criado com sucesso no Fuseki."
                nome_dataset:
                  type: string
                  example: "acervo_fotografico_regional"
      400:
        description: Requisição malformada ou campo 'nome_dataset' ausente.
      401:
        description: Autenticação falhou com o servidor Fuseki (se credenciais forem inválidas).
      409: # Conflict
        description: Dataset com o mesmo nome já existe no Fuseki.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string"}
                message: {"type": "string"}
      500:
        description: Erro interno do servidor ou falha na comunicação com o Fuseki.
    """
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid input", "message": "Request body cannot be empty"}), 400

        nome_dataset_req = data.get('nome_dataset')
        if not nome_dataset_req:
            return jsonify({"error": "Invalid input", "message": "Campo 'nome_dataset' é obrigatório."}), 400

        tipo_dataset_req = data.get('tipo_dataset', 'tdb2')

        # Carregar configurações do Fuseki
        fuseki_base_url = data.get('fuseki_admin_url', config.get('fuseki_url', 'http://localhost:3030')).rstrip('/')
        username = data.get('fuseki_admin_user', config.get('fuseki_admin_user', 'admin'))
        password = data.get('fuseki_admin_password', config.get('fuseki_admin_password'))

        if not password:
             current_app.logger.error("Senha de admin do Fuseki não configurada no servidor.")
             return jsonify({"error": "Server Configuration Error", "message": "Credenciais de admin do Fuseki não configuradas."}), 500

        fuseki_datasets_endpoint = f"{fuseki_base_url}/$/datasets"

        form_payload = {
            'dbName': nome_dataset_req,
            'dbType': tipo_dataset_req
        }

        # Usar requests diretamente para esta chamada, pois não é uma operação SPARQL
        response = requests.post(
            fuseki_datasets_endpoint,
            data=form_payload,
            auth=(username, password),
            timeout=15
        )
        response.raise_for_status()

        if response.status_code == 200:
            if f"/{nome_dataset_req}" in response.text:
                 current_app.logger.info(f"Dataset '{nome_dataset_req}' criado/já existia no Fuseki.")
                 return jsonify({"message": f"Dataset '{nome_dataset_req}' criado ou já existente no Fuseki.", "nome_dataset": nome_dataset_req}), 200
            else:
                 current_app.logger.warning(f"Fuseki retornou 200 mas a resposta não confirma criação para '{nome_dataset_req}': {response.text}")
                 return jsonify({"message": f"Operação de criação do dataset '{nome_dataset_req}' no Fuseki retornou 200, mas a resposta foi inconclusiva.", "details": response.text, "nome_dataset": nome_dataset_req}), 200

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na criação do dataset Fuseki: {http_err} - Resposta: {http_err.response.text}")
        status_code = http_err.response.status_code
        message = http_err.response.text
        if status_code == 401:
            return jsonify({"error": "Fuseki Authentication Failed", "message": "Credenciais de administrador do Fuseki inválidas ou não fornecidas."}), 401
        elif status_code == 409:
             return jsonify({"error": "Conflict", "message": f"Dataset '{nome_dataset_req}' já existe no Fuseki."}), 409
        else:
            return jsonify({
                "error": "Fuseki Operation Failed",
                "message": f"Falha ao criar dataset no Fuseki: {message}",
                "status_code_fuseki": status_code
            }), status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException em criar_dataset_fuseki: {str(e)}")
        return jsonify({"error": "RequestException", "message": f"Erro de comunicação com o servidor Fuseki: {str(e)}"}), 500
    except KeyError as e:
        current_app.logger.error(f"KeyError em criar_dataset_fuseki (configuração?): {str(e)}")
        return jsonify({"error": "Configuration Error", "message": f"Chave de configuração ausente: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em criar_dataset_fuseki: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/meus_repos', methods=['GET'])
@token_required
def meus_repositorios():
    """
    Lista os detalhes completos de todos os repositórios associados ao usuário logado.
    ---
    tags:
      - Repositórios
      - Autenticação
    security:
      - BearerAuth: []
    responses:
      200:
        description: Lista de repositórios do usuário retornada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Repositórios do usuário carregados com sucesso."
                repositorios:
                  type: array
                  items:
                    type: object
                    properties:
                      nome: {"type": "string", "example": "Repositório Principal"}
                      uri: {"type": "string", "format": "uri", "example": "http://localhost:3030/repositorio_principal"}
                      contato: {"type": "string", "example": "contato@repo.org"}
                      descricao: {"type": "string", "example": "Acervo principal da instituição."}
                      responsavel: {"type": "string", "example": "Instituição XYZ"}
                  description: Detalhes dos repositórios aos quais o usuário tem acesso.
      401:
        description: Token não fornecido ou inválido.
      500:
        description: Erro interno no servidor ao buscar repositórios do usuário.
    """
    try:
        user_uri = g.user_uri # Obtém a URI do usuário a partir do decorador token_required

        if not user_uri:
            return jsonify({"message": "URI do usuário não encontrada no contexto da requisição."}), 500

        # 1. Consultar o grafo de usuários para obter os nomes dos repositórios associados a este user_uri
        query_user_repos = f"""
        PREFIX : <http://guara.ueg.br/ontologias/usuarios#>
        SELECT ?repo_name WHERE {{
            <{user_uri}> :repo ?repo_name .
        }}
        """
        current_app.logger.debug(f"Query para repositórios do usuário: {query_user_repos}")

        user_repos_results = execute_sparql_query(USER_QUERY_URL, query_user_repos)

        if not user_repos_results or not user_repos_results.get('results', {}).get('bindings'):
            return jsonify({"message": "Nenhum repositório encontrado para este usuário."}), 200 # Ou 404 se preferir

        repositorio_nomes_associados = [
            binding['repo_name']['value']
            for binding in user_repos_results['results']['bindings']
        ]

        # Remove duplicatas, caso um usuário tenha o mesmo repo listado múltiplas vezes
        repositorio_nomes_associados_unicos = list(set(repositorio_nomes_associados))

        # 2. Para cada nome de repositório, obter os detalhes completos usando obter_repositorio_por_nome
        repositorios_detalhados = []
        for repo_name in repositorio_nomes_associados_unicos:
            repo_details = obter_repositorio_por_nome(repo_name)
            if repo_details:
                repositorios_detalhados.append(repo_details)
            else:
                current_app.logger.warning(f"Detalhes para o repositório '{repo_name}' não encontrados.")

        return jsonify({
            "message": "Repositórios do usuário carregados com sucesso.",
            "repositorios": repositorios_detalhados
        }), 200

    except Exception as e:
        current_app.logger.error(f"Erro ao buscar repositórios do usuário: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
