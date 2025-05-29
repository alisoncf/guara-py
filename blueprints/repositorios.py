from flask import Blueprint, request, jsonify, current_app # Adicionado current_app para logging
import requests
from consultas import get_sparq_repo # get_prefix não é usado diretamente nos endpoints
from config_loader import load_config
from urllib.parse import urlencode
# token_required não é usado neste blueprint específico

repo_app = Blueprint('repo_app', __name__)

# Função auxiliar, não é um endpoint HTTP
def obter_repositorio_por_nome(name):
    """
    Obtém os detalhes de um repositório específico pelo seu nome.
    Esta função chama internamente o endpoint /listar_repositorios.
    """
    # Para evitar dependência cíclica ou chamadas HTTP internas desnecessárias em produção,
    # esta função deveria idealmente realizar a consulta SPARQL diretamente
    # ou ser refatorada se /listar_repositorios for a única fonte.
    # Por ora, mantendo a lógica original de chamar o endpoint.
    
    # Constrói a URL para o endpoint listar_repositorios.
    # Isso assume que o app está rodando e acessível.
    # Em um cenário real, seria melhor ter uma função de serviço que faz a query.
    try:
        # Esta é uma chamada HTTP interna, o que pode não ser ideal.
        # Seria melhor ter uma função que executa a lógica de consulta diretamente.
        listar_url = request.url_root.rstrip('/') + '/repositorios/listar_repositorios'
        response = requests.get(listar_url, params={'name': name}, timeout=5) # Adicionado timeout
        response.raise_for_status() # Levanta erro para status 4xx/5xx
        
        repositorios_data = response.json()

        if "results" in repositorios_data and "bindings" in repositorios_data["results"]:
            for repo_binding in repositorios_data["results"]["bindings"]:
                # A query original em get_sparq_repo() já filtra pelo nome se fornecido.
                # Esta verificação adicional pode ser redundante se a query SPARQL for eficiente.
                if repo_binding.get("nome", {}).get("value", "").lower() == name.lower():
                    return {
                        "nome": repo_binding.get("nome", {}).get("value"),
                        "uri": repo_binding.get("uri", {}).get("value"), # No SPARQL original é ?uri, não ?s
                        "contato": repo_binding.get("contato", {}).get("value"),
                        "descricao": repo_binding.get("descricao", {}).get("value"),
                        "responsavel": repo_binding.get("responsavel", {}).get("value")
                    }
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro ao chamar /listar_repositorios internamente em obter_repositorio_por_nome: {e}")
        return None
    return None

@repo_app.route('/listar_repositorios', methods=['GET'])
def listar_repositorios_endpoint(): # Renomeado de listar_repositorios para evitar conflito
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
            schema: # Schema para resultado JSON SPARQL padrão
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
                          uri: {"type": "object", "properties": {"type": {"type": "string", "example": "uri"}, "value": {"type": "string", "format": "uri", "example": "http://example.org/repo/Repo1"}}}
                          nome: {"type": "object", "properties": {"type": {"type": "string", "example": "literal"}, "value": {"type": "string", "example": "Repositório 1"}}}
                          # Adicionar outras vars conforme a query get_sparq_repo
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
        
        # A query get_sparq_repo() já tem um placeholder %filter%
        # A lógica de filtro deve ser aplicada na query SPARQL, não depois.
        # O placeholder %filter% na query original é problemático se 'nome' não for fornecido.
        # Ajustando a query em consultas.py ou a lógica aqui é necessário.
        # Assumindo que get_sparq_repo() lida com %filter% corretamente (ex: tornando-o vazio se nome_filtro for None)

        # Vamos construir o filtro aqui para maior clareza:
        filtro_sparql = ''
        if nome_filtro:
            # Escapar aspas no nome_filtro para segurança na query
            nome_escaped = nome_filtro.replace('"', '\\"')
            filtro_sparql = f'FILTER(LCASE(STR(?nome)) = LCASE("{nome_escaped}"))'
            # Ou, se a query já espera um nome exato:
            # filtro_sparql = f'FILTER(?nome = "{nome_escaped}"^^xsd:string)'


        cfg = load_config()
        sparqapi_url = cfg.get('repo_query_url')
        if not sparqapi_url:
            current_app.logger.error("Configuração 'repo_query_url' não encontrada.")
            return jsonify({"error": "Configuration Error", "message": "Endpoint de query de repositório não configurado."}), 500

        # Modificar a query para usar o filtro construído
        sparql_query_template = get_sparq_repo() # Espera-se que tenha um SELECT ... WHERE { ... %filtro_aqui% ... }
        sparql_query = sparql_query_template.replace("%filter_aqui%", filtro_sparql) # Usar um placeholder distinto
        
        current_app.logger.debug(f"SPARQL query para listar repositórios: {sparql_query}")
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data_payload = {'query': sparql_query}
        encoded_data = urlencode(data_payload)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        return jsonify(result)

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na query SPARQL (listar_repositorios): {http_err} - Response: {response.text}")
        return jsonify({"error": f"SPARQL query failed", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException em listar_repositorios: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except KeyError as e: # Para erros de config
        current_app.logger.error(f"KeyError em listar_repositorios (configuração?): {str(e)}")
        return jsonify({"error": "Configuration Error", "message": f"Chave de configuração ausente: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em listar_repositorios: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/adicionar_repo', methods=['POST'])
def adicionar_repo_endpoint(): # Renomeado de adicionar_repo
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
              - id_local_repo # Renomeado de 'uri' para clareza
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
                format: email # Ou string genérica se não for sempre email
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
                id_local_repo: # Retornando o ID local usado para criação
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
            if field not in data or not data[field]: # Checa se o campo existe e não é vazio
                return jsonify({"error": "Invalid input", "message": f"Campo '{field}' é obrigatório e não pode ser vazio."}), 400

        cfg = load_config()
        prefix_base_repo_config = cfg.get('prefix_base_repo') # Ex: "http://guara.ueg.br/ontologias/v1/repositoriosamigos#"
        sparql_update_url = cfg.get('repo_update_url') # No config original era 'class_update_url', mas 'repo_update_url' é mais semântico aqui.

        if not prefix_base_repo_config or not sparql_update_url:
            current_app.logger.error("Configurações 'prefix_base_repo' ou 'repo_update_url' não encontradas.")
            return jsonify({"error": "Configuration Error", "message": "Configuração do servidor incompleta."}), 500
        
        if not prefix_base_repo_config.endswith(('#', '/')):
            prefix_base_repo_config += "#"

        id_local = data['id_local_repo'].replace(" ", "_") # Sanitização básica
        repo_uri_completa = f"<{prefix_base_repo_config}{id_local}>"
        
        # A query original usa rpa: para propriedades, mas o prefixo : para a classe.
        # Usaremos rpa: consistentemente para o vocabulário de repositórios.
        # O prefixo : será a base URI do grafo onde os dados são inseridos.
        # Ex: PREFIX : <http://localhost:3030/repositoriosamigos#>
        #     PREFIX rpa: <http://guara.ueg.br/ontologias/v1/repositorios#> (vocabulário)

        # Assumindo que 'repo_update_url' aponta para um dataset específico, ex: /repositoriosamigos/update
        # Então, o prefixo : na query SPARQL deve ser a base desse dataset.
        # Se 'prefix_base_repo' for o vocabulário, e 'repo_update_url' o endpoint,
        # a URI da classe será <prefix_base_repo_config_value><id_local_value>
        # e as propriedades rpa:nome etc.

        sparql_query = f"""
            PREFIX rpa:   <http://guara.ueg.br/ontologias/v1/repositorios#> 
            PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
            PREFIX owl:   <http://www.w3.org/2002/07/owl#> 
            PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
            
            INSERT DATA {{
                {repo_uri_completa} rdf:type owl:NamedIndividual ; # Ou owl:Class se for a intenção
                                    rdf:type rpa:Repositorio ; # Adicionando um tipo específico do vocabulário rpa
                                    rpa:idLocal "{id_local}" ; # Usando id_local como propriedade
                                    rpa:nome "{data['nome'].replace('"', '\\"')}" ;
                                    rpa:contato "{data['contato'].replace('"', '\\"')}" ;
                                    rpa:descricao \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\" ;
                                    rpa:responsavel "{data['responsavel'].replace('"', '\\"')}" .
            }}
        """
        # Nota: A query original criava um owl:Class. Se a intenção é criar instâncias de repositórios,
        # rdf:type owl:NamedIndividual e rdf:type rpa:Repositorio (onde rpa:Repositorio é uma owl:Class) seria mais comum.
        # Mantendo a criação de owl:Class se essa for a modelagem intencional, mas ajustando para usar rdfs:label para nome.
        # Se for owl:Class:
        # sparql_query = f"""
        #     PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
        #     PREFIX owl:   <http://www.w3.org/2002/07/owl#> 
        #     PREFIX rpa:   <http://guara.ueg.br/ontologias/v1/repositorios#> 
            
        #     INSERT DATA {{
        #         {repo_uri_completa} rdf:type owl:Class ;
        #                             rdfs:label "{data['nome'].replace('"', '\\"')}" ;
        #                             rdfs:comment \"\"\"{data['descricao'].replace('"""', '\\"""')}\"\"\" ;
        #                             rpa:contato "{data['contato'].replace('"', '\\"')}" ;
        #                             rpa:responsavel "{data['responsavel'].replace('"', '\\"')}" ;
        #                             rpa:idLocal "{id_local}" . 
        #     }}
        # """

        current_app.logger.debug(f"SPARQL query para adicionar repositório: {sparql_query}")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json', # Aceita JSON para a resposta do update
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        response = requests.post(sparql_update_url, headers=headers, data=encoded_data, timeout=10)
        response.raise_for_status()

        return jsonify({
            "message": "Definição de repositório adicionada com sucesso.", 
            "repositorio_uri": repo_uri_completa.strip("<>"),
            "id_local_repo": id_local
            }), 201

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na atualização SPARQL (adicionar_repo): {http_err} - Response: {response.text}")
        return jsonify({"error": "SPARQL Update Failed", "message": response.text, "status_code": response.status_code}), response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException em adicionar_repo: {str(e)}")
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except KeyError as e:
        current_app.logger.error(f"KeyError em adicionar_repo (configuração?): {str(e)}")
        return jsonify({"error": "Configuration Error", "message": f"Chave de configuração ausente: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em adicionar_repo: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500


@repo_app.route('/create_dataset', methods=['POST'])
def criar_dataset_fuseki(): # Renomeado de criar_dataset
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
          application/json: # A resposta do Fuseki pode variar
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

        # Carregar configurações do Fuseki (idealmente de um arquivo de configuração seguro ou variáveis de ambiente)
        # Estes valores podem ser sobrescritos pelo request se fornecidos, mas é mais seguro pegar da config do servidor.
        cfg = load_config() # Supondo que config.json tenha fuseki_admin_url, user, pass
        fuseki_base_url = data.get('fuseki_admin_url', cfg.get('fuseki_url', 'http://localhost:3030')).rstrip('/')
        username = data.get('fuseki_admin_user', cfg.get('fuseki_admin_user', 'admin')) # Default 'admin'
        password = data.get('fuseki_admin_password', cfg.get('fuseki_admin_password')) # Senha deve vir da config

        if not password: # Senha é crucial
             current_app.logger.error("Senha de admin do Fuseki não configurada no servidor.")
             return jsonify({"error": "Server Configuration Error", "message": "Credenciais de admin do Fuseki não configuradas."}), 500

        fuseki_datasets_endpoint = f"{fuseki_base_url}/$/datasets"

        form_payload = {
            'dbName': nome_dataset_req,
            'dbType': tipo_dataset_req
        }
        
        current_app.logger.info(f"Tentando criar dataset '{nome_dataset_req}' em {fuseki_datasets_endpoint}")
        response = requests.post(
            fuseki_datasets_endpoint,
            data=form_payload,
            auth=(username, password),
            timeout=15 # Timeout para a operação no Fuseki
        )

        # Fuseki retorna 200 OK para sucesso.
        # Se o dataset já existe, ele também retorna 200 OK mas não cria um novo (comportamento pode variar com a versão).
        # É melhor verificar a resposta de texto ou fazer um GET antes/depois para confirmar.
        # Para este exemplo, vamos assumir que 200 é sucesso e não há conflito explícito na resposta de POST.
        if response.status_code == 200:
            # Verificar se a resposta contém alguma indicação de que já existia, se possível
            if f"/{nome_dataset_req}" in response.text: # Heurística simples
                 current_app.logger.info(f"Dataset '{nome_dataset_req}' criado/já existia no Fuseki.")
                 return jsonify({"message": f"Dataset '{nome_dataset_req}' criado ou já existente no Fuseki.", "nome_dataset": nome_dataset_req}), 200
            else: # Resposta inesperada para 200
                 current_app.logger.warning(f"Fuseki retornou 200 mas a resposta não confirma criação para '{nome_dataset_req}': {response.text}")
                 return jsonify({"message": f"Operação de criação do dataset '{nome_dataset_req}' no Fuseki retornou 200, mas a resposta foi inconclusiva.", "details": response.text, "nome_dataset": nome_dataset_req}), 200

        # Tratar outros códigos de status do Fuseki
        elif response.status_code == 401: # Unauthorized
            current_app.logger.error(f"Falha na autenticação com Fuseki para criar dataset '{nome_dataset_req}'.")
            return jsonify({"error": "Fuseki Authentication Failed", "message": "Credenciais de administrador do Fuseki inválidas ou não fornecidas."}), 401
        elif response.status_code == 409: # Conflict (se Fuseki explicitamente retornar isso)
             current_app.logger.warning(f"Dataset '{nome_dataset_req}' já existe no Fuseki (409).")
             return jsonify({"error": "Conflict", "message": f"Dataset '{nome_dataset_req}' já existe no Fuseki."}), 409
        else:
            current_app.logger.error(f"Erro ao criar dataset '{nome_dataset_req}' no Fuseki: {response.status_code} - {response.text}")
            return jsonify({
                "error": "Fuseki Operation Failed",
                "message": f"Falha ao criar dataset no Fuseki: {response.text}",
                "status_code_fuseki": response.status_code
            }), response.status_code

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"RequestException em criar_dataset_fuseki: {str(e)}")
        return jsonify({"error": "RequestException", "message": f"Erro de comunicação com o servidor Fuseki: {str(e)}"}), 500
    except KeyError as e: # Para erros de config
        current_app.logger.error(f"KeyError em criar_dataset_fuseki (configuração?): {str(e)}")
        return jsonify({"error": "Configuration Error", "message": f"Chave de configuração ausente: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em criar_dataset_fuseki: {str(e)}")
        return jsonify({"error": "Exception", "message": str(e)}), 500

