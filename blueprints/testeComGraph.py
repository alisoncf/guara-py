from flask import Flask, jsonify, request, current_app # Adicionado current_app para logging, embora não usado ativamente aqui
from rdflib import Graph, URIRef, Literal, RDF, OWL, RDFS
from rdflib.namespace import Namespace, NamespaceManager
import requests # Adicionado para uma melhor gestão de erros HTTP na função load_rdf_graph

# Este ficheiro parece ser uma aplicação Flask autónoma.
# Se fosse um blueprint para ser registado numa app maior, a instanciação de 'app' seria diferente.
app = Flask(__name__)

# Configuração do namespace da microontologia
CMGC_NAMESPACE_STR = "http://www.guara.ueg.br/ontologias/v1/cmgclass#"
cmgc = Namespace(CMGC_NAMESPACE_STR)

# Configuração do TDB (endpoint Fuseki para consulta)
# Idealmente, isto viria de um ficheiro de configuração.
FUSEKI_QUERY_URL = "http://200.137.241.247:8080/fuseki/mplclasses/query" # Endpoint de consulta
FUSEKI_UPDATE_URL = "http://200.137.241.247:8080/fuseki/mplclasses/update" # Endpoint de atualização (para POST)


def load_rdf_graph():
    """
    Carrega o grafo RDF a partir do endpoint Fuseki especificado.
    Retorna um objeto Graph da rdflib.
    Lança exceções em caso de erro ao aceder ou analisar o RDF.
    """
    graph = Graph()
    graph.namespace_manager.bind("cmgc", cmgc) # Bind do prefixo para serialização/queries
    
    headers = {'Accept': 'text/turtle,*/*;q=0.9'} # Preferir Turtle, mas aceitar outros
    try:
        # Para carregar o grafo, geralmente faz-se uma query CONSTRUCT ou DESCRIBE,
        # ou acede-se a um endpoint de "get graph" se o Fuseki o expuser diretamente para o dataset.
        # graph.parse(source=FUSEKI_QUERY_URL) pode não funcionar como esperado se FUSEKI_QUERY_URL for um endpoint SPARQL.
        # Uma abordagem mais robusta seria fazer uma query CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }.
        # Para simplificar e manter próximo do original, vamos assumir que o parse funciona ou que
        # o endpoint FUSEKI_QUERY_URL (ou um similar FUSEKI_DATA_URL) serve o grafo diretamente.
        # Se FUSEKI_QUERY_URL é um endpoint SPARQL, o parse direto não é a forma correta de carregar o grafo inteiro.
        
        # Exemplo de como carregar via query CONSTRUCT:
        # sparql_construct_query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
        # response = requests.post(FUSEKI_QUERY_URL, data={'query': sparql_construct_query}, headers={'Accept': 'text/turtle'})
        # response.raise_for_status()
        # graph.parse(data=response.text, format="turtle")
        
        # Mantendo a lógica original de parse direto, mas com melhor tratamento de erro:
        # Nota: Se FUSEKI_QUERY_URL é um endpoint /sparql ou /query, graph.parse(source=URL) não vai carregar o grafo.
        # Ele tentaria interpretar a resposta HTML do formulário SPARQL como RDF.
        # É necessário um endpoint que sirva o grafo diretamente (ex: /get ou /data).
        # Vamos assumir que FUSEKI_QUERY_URL foi ajustado para um endpoint de dados, se necessário.
        # Para este exemplo, vamos simular que o parse funciona, mas na prática isso precisa de atenção.
        
        # Se o objetivo é apenas executar queries, não é preciso carregar o grafo inteiro na memória primeiro.
        # As queries podem ser enviadas diretamente ao endpoint SPARQL.
        # A função load_rdf_graph() como está, sugere manipulação local do grafo após carregá-lo.
        
        # Dado que as rotas usam graph.query() e graph.serialize(), carregar o grafo é a intenção.
        # A URL original "http://200.137.241.247:8080/fuseki/mplclasses" sugere o nome do dataset,
        # que pode ter um endpoint de dados em /data ou /get. Ex: .../mplclasses/data
        
        fuseki_data_endpoint = FUSEKI_QUERY_URL.replace("/query", "/data") # Suposição comum para Fuseki
        
        #app.logger.info(f"A carregar grafo de: {fuseki_data_endpoint}")
        response = requests.get(fuseki_data_endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        graph.parse(data=response.text, format="turtle") # Assumindo que o endpoint de dados retorna Turtle

    except requests.exceptions.HTTPError as http_err:
        #app.logger.error(f"Erro HTTP ao carregar grafo RDF de {fuseki_data_endpoint}: {http_err} - {response.text}")
        raise ConnectionError(f"Erro HTTP ao aceder ao repositório RDF: {http_err} (Status: {response.status_code})")
    except requests.exceptions.RequestException as req_err:
        #app.logger.error(f"Erro de rede ao carregar grafo RDF de {fuseki_data_endpoint}: {req_err}")
        raise ConnectionError(f"Erro de rede ao aceder ao repositório RDF: {req_err}")
    except Exception as e: # Outros erros de parse, etc.
        #app.logger.error(f"Erro ao analisar RDF de {fuseki_data_endpoint}: {e}")
        raise ValueError(f"Erro ao analisar os dados RDF: {e}")
    return graph

@app.route('/acervo/classes', methods=['GET'])
def listar_classes_acervo():
    """
    Lista as classes da ontologia do acervo (exceto cmgc:Acervo).
    Retorna URI, rótulo (label), comentário e superclasse (se houver).
    ---
    tags:
      - Classes do Acervo
    responses:
      200:
        description: Lista de classes da ontologia do acervo retornada com sucesso.
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  uri:
                    type: string
                    format: uri
                    description: URI da classe.
                    example: "http://www.guara.ueg.br/ontologias/v1/cmgclass#Documento"
                  label:
                    type: string
                    description: Rótulo (nome legível) da classe.
                    example: "Documento"
                  comentario:
                    type: string
                    description: Descrição ou comentário associado à classe.
                    example: "Classe que representa documentos textuais do acervo."
                  classe_mae:
                    type: string
                    format: uri
                    nullable: true
                    description: URI da superclasse direta, se existir.
                    example: "http://www.guara.ueg.br/ontologias/v1/cmgclass#ItemDeAcervo"
      500:
        description: Erro ao carregar o grafo RDF do repositório ou ao executar a consulta SPARQL.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Erro de Conexão com Repositório RDF"
                message:
                  type: string
                  example: "Detalhes do erro..."
      503: # Service Unavailable
        description: Repositório RDF (Fuseki) indisponível ou não configurado corretamente.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Repositório Indisponível"
                message:
                  type: string
    """
    try:
        # Em vez de carregar o grafo inteiro para uma query SELECT, é mais eficiente
        # enviar a query diretamente ao endpoint SPARQL.
        
        query = f"""
            PREFIX cmgc: <{CMGC_NAMESPACE_STR}>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>

            SELECT ?classe ?label ?comentario ?classe_mae
            WHERE {{
                ?classe rdf:type owl:Class ;
                        rdfs:label ?label ;
                        rdfs:comment ?comentario .
                OPTIONAL {{
                    ?classe rdfs:subClassOf ?classe_mae_raw .
                    # Filtrar para que classe_mae seja uma URI e não um blank node, e que não seja owl:Thing implicitamente
                    FILTER(isURI(?classe_mae_raw) && ?classe_mae_raw != owl:Thing)
                }}
                FILTER (?classe != cmgc:Acervo)
                BIND(COALESCE(?classe_mae_raw, "") AS ?classe_mae) # Retorna string vazia se não houver classe_mae
            }}
            ORDER BY ?label
        """
        
        headers = {'Accept': 'application/sparql-results+json'}
        payload = {'query': query}
        
        #app.logger.info(f"A executar query SPARQL em {FUSEKI_QUERY_URL}: {query}")
        response = requests.post(FUSEKI_QUERY_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        results_json = response.json()
        classes = []
        for result in results_json.get("results", {}).get("bindings", []):
            classe_mae_val = result.get('classe_mae', {}).get('value')
            classes.append({
                'uri': result.get('classe', {}).get('value'),
                'label': result.get('label', {}).get('value'),
                'comentario': result.get('comentario', {}).get('value'),
                'classe_mae': classe_mae_val if classe_mae_val else None # Converte string vazia para None
            })
        return jsonify(classes)

    except requests.exceptions.HTTPError as http_err:
        #app.logger.error(f"Erro HTTP ao consultar classes: {http_err} - {response.text}")
        return jsonify({"error": "Erro na Consulta SPARQL", "message": f"O servidor RDF retornou o status {response.status_code}.", "details": response.text}), response.status_code
    except requests.exceptions.RequestException as req_err:
        #app.logger.error(f"Erro de rede ao consultar classes: {req_err}")
        return jsonify({"error": "Erro de Conexão com Repositório RDF", "message": str(req_err)}), 503
    except Exception as e:
        #app.logger.error(f"Erro inesperado ao listar classes: {e}")
        return jsonify({"error": "Erro Interno do Servidor", "message": str(e)}), 500


@app.route('/acervo/classe', methods=['POST'])
def adicionar_classe_acervo():
    """
    Adiciona uma nova classe à ontologia do acervo no repositório Fuseki.
    ---
    tags:
      - Classes do Acervo
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - label
              - comentario
            properties:
              label:
                type: string
                description: Rótulo (nome legível) para a nova classe. Será usado para gerar parte da URI.
                example: "Documento Raro"
              comentario:
                type: string
                description: Descrição ou comentário sobre a nova classe.
                example: "Classe para documentos de especial valor histórico ou raridade."
              classe_mae_uri: # URI completa da superclasse
                type: string
                format: uri
                nullable: true
                description: URI completa da superclasse à qual esta nova classe será subordinada (opcional).
                example: "http://www.guara.ueg.br/ontologias/v1/cmgclass#Documento"
    responses:
      201:
        description: Classe adicionada com sucesso ao repositório.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Classe adicionada com sucesso."
                nova_classe_uri:
                  type: string
                  format: uri
                  example: "http://www.guara.ueg.br/ontologias/v1/cmgclass#DocumentoRaro"
      400:
        description: Dados de entrada inválidos ou campos obrigatórios ausentes.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Dados Inválidos"}
                message: {"type": "string", "example": "Campo 'label' é obrigatório."}
      500:
        description: Erro ao processar a adição da classe ou ao comunicar com o repositório Fuseki.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Erro na Atualização SPARQL"}
                message: {"type": "string"}
      503: # Service Unavailable
        description: Repositório RDF (Fuseki) indisponível.
        content:
          application/json:
            schema:
              type: object
              properties:
                error: {"type": "string", "example": "Repositório Indisponível"}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados Inválidos', 'message': 'Corpo da requisição não pode ser vazio.'}), 400

    label = data.get('label')
    comentario = data.get('comentario')
    classe_mae_uri_param = data.get('classe_mae_uri') # Espera URI completa

    if not label or not comentario: # Label e comentário são essenciais
        return jsonify({'error': 'Dados Inválidos', 'message': "Campos 'label' e 'comentario' são obrigatórios."}), 400

    # Gerando URI para a nova classe (deve ser única)
    # Sanitizar o label para formar parte da URI
    uri_label_part = label.replace(" ", "_").replace("-", "_").replace("'", "").replace("\"", "")
    nova_classe_uri_completa = f"<{CMGC_NAMESPACE_STR}{uri_label_part}>"
    
    # Construir triplas para a query INSERT DATA
    triples = [
        f"{nova_classe_uri_completa} rdf:type owl:Class",
        f"{nova_classe_uri_completa} rdfs:label \"{label.replace('"', '\\"')}\"", # Escapar aspas no label
        f"{nova_classe_uri_completa} rdfs:comment \"\"\"{comentario.replace('"""', '\\"""')}\"\"\"" # Escapar aspas triplas no comentário
    ]

    if classe_mae_uri_param:
        # Validar se é uma URI (simplificado)
        if not (classe_mae_uri_param.startswith("http://") or classe_mae_uri_param.startswith("https://")):
             return jsonify({'error': 'Dados Inválidos', 'message': "Formato inválido para 'classe_mae_uri'."}), 400
        triples.append(f"{nova_classe_uri_completa} rdfs:subClassOf <{classe_mae_uri_param}>")

    sparql_update_query = f"""
        PREFIX cmgc: <{CMGC_NAMESPACE_STR}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        INSERT DATA {{
            { ' .\n'.join(triples) } .
        }}
    """
    
    headers = {'Content-Type': 'application/sparql-update'} # Ou application/x-www-form-urlencoded para data={'update': query}
    
    try:
        #app.logger.info(f"A executar SPARQL Update em {FUSEKI_UPDATE_URL}: {sparql_update_query}")
        # Para 'application/sparql-update', o corpo da requisição é a query diretamente
        response = requests.post(FUSEKI_UPDATE_URL, data=sparql_update_query.encode('utf-8'), headers=headers, timeout=10)
        response.raise_for_status() # Levanta erro para 4xx/5xx
        
        return jsonify({
            'message': 'Classe adicionada com sucesso.',
            'nova_classe_uri': nova_classe_uri_completa.strip("<>")
            }), 201

    except requests.exceptions.HTTPError as http_err:
        #app.logger.error(f"Erro HTTP ao adicionar classe: {http_err} - {response.text}")
        return jsonify({"error": "Erro na Atualização SPARQL", "message": f"O servidor RDF retornou o status {response.status_code}.", "details": response.text}), response.status_code
    except requests.exceptions.RequestException as req_err:
        #app.logger.error(f"Erro de rede ao adicionar classe: {req_err}")
        return jsonify({"error": "Erro de Conexão com Repositório RDF", "message": str(req_err)}), 503
    except Exception as e:
        #app.logger.error(f"Erro inesperado ao adicionar classe: {e}")
        return jsonify({'error': "Erro Interno do Servidor", 'message': str(e)}), 500


# Execução do aplicativo Flask (se for para ser executado autonomamente)
if __name__ == '__main__':
    # Para Flasgger funcionar corretamente com `app.run`, ele precisa ser inicializado antes.
    # from flasgger import Swagger
    # swagger = Swagger(app) # Inicializar Swagger se for executar autonomamente
    app.run(debug=True, port=5001) # Usar uma porta diferente se a principal já estiver em 5000

