from flask import Blueprint, request, jsonify, current_app
import requests
import os
import uuid # Não usado diretamente nos endpoints atuais, mas pode ser útil para futuras expansões
from urllib.parse import urlencode

# Importar de consultas se get_prefix for necessário para construir queries manualmente
# from consultas import get_prefix
# from config_loader import load_config # Não usado diretamente aqui

midiaapi_app = Blueprint('midiaapi_app', __name__)

@midiaapi_app.route('/list', methods=['GET'])
def listar_midias_objeto(): # Renomeado de listar_arquivos para especificidade
    """
    Lista arquivos de mídia locais associados a um objeto e suas URIs correspondentes
    registradas em um repositório SPARQL via schema:associatedMedia.
    ---
    tags:
      - Mídia
      - Objetos Digitais # Ou a tag mais apropriada para 'objetoId'
    parameters:
      - name: objetoId
        in: query
        type: string
        required: true
        description: ID do objeto para o qual as mídias serão listadas.
        example: "objeto123-uuid-456"
      - name: repositorio_sparql_endpoint # Renomeado de 'repositorio' para clareza
        in: query
        type: string
        format: uri
        required: true
        description: URL completa do endpoint SPARQL do repositório para consulta das mídias associadas.
        example: "http://localhost:3030/meu_dataset/sparql"
      - name: repositorio_base_uri # Novo parâmetro para construir URIs de objeto
        in: query
        type: string
        format: uri
        required: true
        description: URI base do repositório (ex http://meudominio.com/objetos#) usada para montar a URI do objeto na consulta SPARQL.
        example: "http://localhost:3030/meu_dataset#"

    responses:
      200:
        description: Lista de mídias locais e suas informações do SPARQL retornada com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                objeto_id_consultado:
                  type: string
                  example: "objeto123-uuid-456"
                path_pasta_uploads:
                  type: string
                  description: Caminho absoluto no servidor para a pasta de uploads do objeto.
                  example: "/var/www/imagens/objeto123-uuid-456"
                arquivos_locais:
                  type: array
                  items:
                    type: string
                  description: Lista de nomes de arquivos encontrados na pasta de uploads do objeto.
                  example: ["foto_evento.jpg", "video_reportagem.mp4", "documento_scan.pdf"]
                midias_associadas_sparql:
                  type: array
                  items:
                    type: object
                    properties:
                      media_uri:
                        type: string
                        format: uri
                        description: URI da mídia conforme registrada no SPARQL.
                        example: "http://example.org/media/foto_evento.jpg"
                      objeto_associado_uri: # ?a da query original
                        type: string
                        format: uri
                        description: URI do objeto ao qual a mídia está associada.
                        example: "http://localhost:3030/meu_dataset#objeto123-uuid-456"
                  description: Lista de mídias encontradas no SPARQL associadas ao objetoId.
                arquivos_combinados:
                  type: array
                  items:
                    type: object
                    properties:
                      nome_arquivo_local:
                        type: string
                        description: Nome do arquivo encontrado localmente.
                        example: "foto_evento.jpg"
                      uri_sparql_correspondente:
                        type: string
                        format: uri
                        nullable: true
                        description: URI da mídia no SPARQL que corresponde ao arquivo local (se houver).
                        example: "http://example.org/media/foto_evento.jpg"
                      presente_localmente:
                        type: boolean
                        description: Indica se o arquivo foi encontrado na pasta de uploads.
                      presente_sparql:
                        type: boolean
                        description: Indica se uma URI correspondente foi encontrada no SPARQL.
                  description: "Lista consolidada de mídias, mostrando correspondência entre arquivos locais e registros SPARQL."
      400:
        description: Parâmetros de consulta inválidos ou ausentes.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Invalid input"
                message:
                  type: string
                  example: "Parâmetro 'objetoId' é obrigatório."
      404:
        description: Pasta de uploads do objeto não encontrada no servidor.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Not Found"
                message:
                  type: string
                  example: "Pasta de uploads para o objetoId especificado não encontrada."
      500:
        description: Erro interno no servidor ou falha na configuração.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "Server Configuration Error / RequestException"
                message:
                  type: string
                  example: "UPLOAD_FOLDER não configurado ou falha na comunicação SPARQL."
    """
    try:
        objeto_id = request.args.get('objetoId')
        repo_sparql_endpoint = request.args.get('repositorio_sparql_endpoint')
        repo_base_uri = request.args.get('repositorio_base_uri')


        if not objeto_id:
            return jsonify({"error": "Invalid input", "message": "Parâmetro 'objetoId' é obrigatório."}), 400
        if not repo_sparql_endpoint:
            return jsonify({"error": "Invalid input", "message": "Parâmetro 'repositorio_sparql_endpoint' é obrigatório."}), 400
        if not repo_base_uri:
            return jsonify({"error": "Invalid input", "message": "Parâmetro 'repositorio_base_uri' é obrigatório."}), 400

        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"
        
        objeto_uri_completa = f"<{repo_base_uri}{objeto_id}>"

        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            current_app.logger.error("UPLOAD_FOLDER não está configurado na aplicação.")
            return jsonify({"error": "Server Configuration Error", "message": "UPLOAD_FOLDER não configurado."}), 500
            
        objeto_folder_path = os.path.join(upload_folder, str(objeto_id))
        
        arquivos_locais_lista = []
        if os.path.exists(objeto_folder_path) and os.path.isdir(objeto_folder_path):
            arquivos_locais_lista = os.listdir(objeto_folder_path)
        # else:
            # Considerar retornar 404 se a pasta do objeto não existe,
            # mas ainda pode haver mídias associadas apenas no SPARQL.
            # current_app.logger.info(f"Pasta de uploads não encontrada: {objeto_folder_path}")

        # Query SPARQL para buscar mídias associadas ao objetoId
        sparql_query = f"""
            PREFIX schema: <http://schema.org/>
            SELECT ?objeto_associado_uri ?media_uri
            WHERE {{ 
                {objeto_uri_completa} schema:associatedMedia ?media_uri .
                BIND({objeto_uri_completa} AS ?objeto_associado_uri)
            }}
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        payload_data = {'query': sparql_query}
        encoded_payload = urlencode(payload_data)

        midias_sparql_lista = []
        sparql_response_status = "N/A"
        sparql_response_text = "N/A"

        try:
            response = requests.post(repo_sparql_endpoint, headers=headers, data=encoded_payload, timeout=10)
            sparql_response_status = response.status_code
            sparql_response_text = response.text
            response.raise_for_status() # Levanta HTTPError para códigos 4xx/5xx
            
            sparql_result_json = response.json()
            for item in sparql_result_json.get("results", {}).get("bindings", []):
                media_uri = item.get("media_uri", {}).get("value")
                obj_assoc_uri = item.get("objeto_associado_uri", {}).get("value")
                if media_uri:
                    midias_sparql_lista.append({
                        "media_uri": media_uri,
                        "objeto_associado_uri": obj_assoc_uri
                    })
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Erro na consulta SPARQL para {repo_sparql_endpoint}: {str(e)}")
            # Não retornar erro fatal, continuar para combinar com arquivos locais se houver

        # Combinar resultados
        arquivos_combinados_map = {}

        # Adicionar arquivos locais ao mapa
        for nome_local in arquivos_locais_lista:
            arquivos_combinados_map[nome_local] = {
                "nome_arquivo_local": nome_local,
                "uri_sparql_correspondente": None,
                "presente_localmente": True,
                "presente_sparql": False
            }
        
        # Adicionar/Atualizar com informações do SPARQL
        for midia_sparql in midias_sparql_lista:
            uri_sparql = midia_sparql["media_uri"]
            nome_arquivo_da_uri = uri_sparql.split("/")[-1] # Heurística

            if nome_arquivo_da_uri in arquivos_combinados_map:
                arquivos_combinados_map[nome_arquivo_da_uri]["uri_sparql_correspondente"] = uri_sparql
                arquivos_combinados_map[nome_arquivo_da_uri]["presente_sparql"] = True
            else: # Mídia existe no SPARQL mas não foi encontrada localmente com esse nome
                arquivos_combinados_map[uri_sparql] = { # Usar URI como chave se não houver nome local
                    "nome_arquivo_local": nome_arquivo_da_uri, # Ou None se preferir
                    "uri_sparql_correspondente": uri_sparql,
                    "presente_localmente": False,
                    "presente_sparql": True
                }
        
        return jsonify({
            "objeto_id_consultado": objeto_id,
            "path_pasta_uploads": objeto_folder_path if os.path.exists(objeto_folder_path) else "Pasta não encontrada",
            "arquivos_locais": arquivos_locais_lista,
            "midias_associadas_sparql": midias_sparql_lista,
            "arquivos_combinados": list(arquivos_combinados_map.values()),
            # Para depuração, pode ser útil retornar o status da chamada SPARQL
            # "debug_sparql_status": sparql_response_status,
            # "debug_sparql_response": sparql_response_text if sparql_response_status != 200 else "OK"
        })
        
    except requests.exceptions.HTTPError as http_err: # Erros específicos da resposta HTTP do SPARQL
        current_app.logger.error(f"Erro HTTP na consulta SPARQL: {http_err}")
        return jsonify({"error": "SPARQL Query HTTP Error", "message": str(http_err), "details": sparql_response_text}), sparql_response_status
    except requests.exceptions.RequestException as req_err: # Outros erros de request (conexão, timeout)
        current_app.logger.error(f"Erro de Requisição ao SPARQL: {req_err}")
        return jsonify({"error": "RequestException", "message": f"Falha na comunicação com o endpoint SPARQL: {str(req_err)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em listar_midias_objeto: {str(e)}")
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


