from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import shutil
from werkzeug.utils import secure_filename
# Removido 'requests' e 'urlencode' pois agora serão gerenciados por 'utils'

# Importar as funções refatoradas de utils.py
from utils import execute_sparql_query, execute_sparql_update # execute_sparql_query pode não ser diretamente usado aqui, mas é bom ter

# Assumindo que get_prefix é importado se necessário (e parece ser para construir queries)
from consultas import get_prefix
from blueprints.auth import token_required


uploadapp = Blueprint('uploadapi', __name__)

# A função _execute_sparql_update local foi removida,
# pois agora usaremos a versão centralizada de utils.py


@uploadapp.route('/upload', methods=['POST'])
@token_required # Proteger o endpoint de upload
def upload_files_and_associate(): # Renomeado de upload_files
    """
    Realiza o upload de ficheiros de mídia e/ou associa links externos a um objeto existente.
    As mídias são associadas semanticamente ao objeto usando schema:associatedMedia.
    ---
    tags:
      - Mídia
      - Upload
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        multipart/form-data:
          schema:
            type: object
            required:
              - objeto_id
              - repository_update_url # URL do endpoint SPARQL de UPDATE
              - repository_base_uri # URI base para o objeto (ex http://meudominio.com/objetos#)
            properties:
              objeto_id:
                type: string
                description: ID local do objeto ao qual as mídias serão associadas.
                example: "objetoAlfa123"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de ATUALIZAÇÃO do repositório.
                example: "http://localhost:3030/meudataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base do repositório para construir a URI do objeto (ex http://meudominio.com/objetos#).
                example: "http://localhost:3030/meudataset#"
              links_externos: # Renomeado de 'links'
                type: array
                items:
                  type: string
                  format: uri
                description: Lista de URLs de mídias externas a serem associadas.
                example: ["http://example.com/video.mp4", "http://images.example.com/foto.jpg"]
              arquivos_midia: # Renomeado de 'midias'
                type: array
                items:
                  type: string
                  format: binary
                description: Ficheiros de mídia a serem enviados.
          encoding: # Especificar encoding para multipart, especialmente para arquivos_midia
            arquivos_midia:
              contentType: "image/jpeg, image/png, video/mp4, application/pdf" # Exemplos de tipos aceites
    responses:
      200:
        description: Mídias associadas com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Mídias associadas com sucesso."
                objeto_uri:
                  type: string
                  format: uri
                associacoes_sucesso:
                  type: array
                  items:
                    type: string
                    format: uri
                  example: ["http://localhost:3030/media/objetoAlfa123/imagem_uuid.jpg"]
                associacoes_falha:
                  type: array
                  items:
                    type: object
                    properties:
                      media_identificador: {"type": "string"}
                      erro: {"type": "string"}
      400:
        description: Requisição inválida, incompleta ou nenhum ficheiro/link válido enviado.
      401:
        description: Não autorizado (token ausente ou inválido).
      500:
        description: Erro interno ao processar o upload, configurar pastas ou ao associar a mídia via SPARQL.
    """
    try:
        objeto_id_local = request.form.get('objeto_id')
        repo_update_url = request.form.get('repository_update_url')
        repo_base_uri = request.form.get('repository_base_uri')

        links_externos_list = request.form.getlist('links_externos')
        arquivos_midia_list = request.files.getlist('arquivos_midia')

        if not objeto_id_local or not repo_update_url or not repo_base_uri:
            return jsonify({'error': "Campos 'objeto_id', 'repository_update_url' e 'repository_base_uri' são obrigatórios."}), 400

        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"

        objeto_uri_completa = f"<{repo_base_uri}{objeto_id_local}>"

        upload_folder_config = current_app.config.get('UPLOAD_FOLDER')
        media_base_url_config = current_app.config.get('MEDIA_BASE_URL', '/media') # URL base pública para as mídias

        if not upload_folder_config:
            current_app.logger.error("UPLOAD_FOLDER não configurado.")
            return jsonify({'error': 'Configuração do servidor pendente (UPLOAD_FOLDER).'}), 500

        objeto_media_folder = os.path.join(upload_folder_config, str(objeto_id_local))
        if not os.path.exists(objeto_media_folder):
            os.makedirs(objeto_media_folder, exist_ok=True)

        arquivos_validos = [f for f in arquivos_midia_list if f and f.filename and f.filename.strip() != '']
        if not arquivos_validos and not links_externos_list:
            return jsonify({'error': 'Nenhuma mídia válida ou link externo enviado.'}), 400

        associacoes_sucesso = []
        associacoes_falha = []

        # Processar arquivos de mídia enviados
        for file_storage in arquivos_validos:
            original_filename = secure_filename(file_storage.filename)
            extension = os.path.splitext(original_filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{extension}"
            file_path_on_disk = os.path.join(objeto_media_folder, unique_filename)

            try:
                file_storage.save(file_path_on_disk)

                # Construir URL pública para a mídia
                # Assegurar que media_base_url_config não tenha / no final e objeto_id_local não tenha no início se concatenado
                public_media_url = f"{media_base_url_config.rstrip('/')}/{objeto_id_local}/{unique_filename}"
                media_uri_to_add = f"<{public_media_url}>" # URI completa para o RDF

                sparql_insert_media = f"""{get_prefix()}
                    INSERT DATA {{
                        {objeto_uri_completa} schema:associatedMedia {media_uri_to_add} .
                    }}
                """
                current_app.logger.debug(f"SPARQL insert media: {sparql_insert_media}") # Adicionado log
                execute_sparql_update(repo_update_url, sparql_insert_media) # Usar execute_sparql_update
                associacoes_sucesso.append(public_media_url)
            except Exception as e:
                current_app.logger.error(f"Falha ao guardar ou associar ficheiro {original_filename}: {str(e)}")
                associacoes_falha.append({"media_identificador": original_filename, "erro": str(e)})

        # Processar links externos
        for link_url in links_externos_list:
            if link_url.strip(): # Ignorar links vazios
                try:
                    media_uri_to_add = f"<{link_url.strip()}>" # Usar o link diretamente como URI
                    sparql_insert_link = f"""{get_prefix()}
                        INSERT DATA {{
                            {objeto_uri_completa} schema:associatedMedia {media_uri_to_add} .
                        }}
                    """
                    current_app.logger.debug(f"SPARQL insert link: {sparql_insert_link}") # Adicionado log
                    execute_sparql_update(repo_update_url, sparql_insert_link) # Usar execute_sparql_update
                    associacoes_sucesso.append(link_url.strip())
                except Exception as e:
                    current_app.logger.error(f"Falha ao associar link externo {link_url}: {str(e)}")
                    associacoes_falha.append({"media_identificador": link_url, "erro": str(e)})

        return jsonify({
            'message': 'Processamento de mídias concluído.',
            'objeto_uri': objeto_uri_completa.strip("<>"),
            'associacoes_sucesso': associacoes_sucesso,
            'associacoes_falha': associacoes_falha
        }), 200

    except Exception as e: # Captura exceções gerais
        current_app.logger.error(f"Erro geral no endpoint /upload: {str(e)}")
        # Tratamento de erro mais específico se a exceção vier de utils.py
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({'error': 'Erro interno no servidor ao processar upload.', 'details': str(e)}), 500


@uploadapp.route('/remove', methods=['POST']) # Usar DELETE seria mais semântico, mas o original é POST
@token_required # Proteger o endpoint de remoção
def remove_media_association_and_file(): # Renomeado de remove_file
    """
    Remove uma associação de mídia de um objeto (schema:associatedMedia) e move o ficheiro
    local correspondente para uma pasta de "excluídos".
    ---
    tags:
      - Mídia
      - Upload
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - objeto_id
              - media_uri_to_remove # URI da mídia a ser desassociada
              - repository_update_url
              - repository_base_uri
            properties:
              objeto_id:
                type: string
                description: ID local do objeto do qual a mídia será desassociada.
                example: "objetoAlfa123"
              media_uri_to_remove:
                type: string
                format: uri
                description: URI completa da mídia a ser desassociada e potencialmente removida.
                example: "http://localhost:3030/media/objetoAlfa123/imagem_uuid.jpg"
              repository_update_url:
                type: string
                format: uri
                description: URL do endpoint SPARQL de ATUALIZAÇÃO do repositório.
                example: "http://localhost:3030/meudataset/update"
              repository_base_uri:
                type: string
                format: uri
                description: URI base do repositório para construir a URI do objeto.
                example: "http://localhost:3030/meudataset#"
              # O parâmetro 'file' original referia-se ao nome do ficheiro.
              # Agora, 'media_uri_to_remove' é mais preciso para a operação RDF.
              # O nome do ficheiro local será derivado desta URI se for uma mídia local.
    responses:
      200:
        description: Associação de mídia removida e ficheiro movido (se aplicável) com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Associação de mídia removida e ficheiro movido para excluídos."
                media_uri_removida:
                  type: string
                  format: uri
                ficheiro_movido:
                  type: string
                  nullable: true # Pode ser null se a URI não for de um ficheiro local gerido
                  example: "imagem_uuid.jpg"
      400:
        description: Requisição inválida (ex campos obrigatórios ausentes).
      401:
        description: Não autorizado.
      404:
        description: Associação de mídia não encontrada no RDF ou ficheiro local não encontrado.
      500:
        description: Erro interno ao remover a relação SPARQL ou ao mover o ficheiro.
    """
    try:
        data = request.get_json()
        if not data: return jsonify({'error': 'Corpo da requisição não pode ser vazio.'}), 400

        objeto_id_local = data.get('objeto_id')
        media_uri_to_remove_param = data.get('media_uri_to_remove')
        repo_update_url = data.get('repository_update_url')
        repo_base_uri = data.get('repository_base_uri')

        if not all([objeto_id_local, media_uri_to_remove_param, repo_update_url, repo_base_uri]):
            return jsonify({'error': "Campos 'objeto_id', 'media_uri_to_remove', 'repository_update_url' e 'repository_base_uri' são obrigatórios."}), 400

        if not repo_base_uri.endswith(('#', '/')):
            repo_base_uri += "#"

        objeto_uri_completa = f"<{repo_base_uri}{objeto_id_local}>"
        media_uri_rdf_format = f"<{media_uri_to_remove_param}>" # URI completa da mídia

        # 1. Remover a relação SPARQL
        sparql_delete_media = f"""{get_prefix()}
            DELETE DATA {{
                {objeto_uri_completa} schema:associatedMedia {media_uri_rdf_format} .
            }}
        """
        current_app.logger.debug(f"SPARQL delete media: {sparql_delete_media}") # Adicionado log
        execute_sparql_update(repo_update_url, sparql_delete_media) # Usar execute_sparql_update

        # 2. Mover o ficheiro local, se a URI corresponder a um ficheiro gerido localmente
        ficheiro_movido_nome = None
        upload_folder_config = current_app.config.get('UPLOAD_FOLDER')
        media_base_url_config = current_app.config.get('MEDIA_BASE_URL', '/media').rstrip('/')

        # Tentar extrair o nome do ficheiro da URI, assumindo a estrutura {media_base_url}/{objeto_id}/{filename}
        expected_prefix = f"{media_base_url_config}/{objeto_id_local}/"
        if media_uri_to_remove_param.startswith(expected_prefix):
            filename_to_move = media_uri_to_remove_param[len(expected_prefix):]

            if upload_folder_config and filename_to_move:
                objeto_media_folder = os.path.join(upload_folder_config, str(objeto_id_local))
                current_file_path = os.path.join(objeto_media_folder, filename_to_move)

                if os.path.exists(current_file_path):
                    pasta_excluidos = os.path.join(objeto_media_folder, "excluidos")
                    if not os.path.exists(pasta_excluidos):
                        os.makedirs(pasta_excluidos, exist_ok=True)

                    destino_path = os.path.join(pasta_excluidos, filename_to_move)

                    # Evitar sobrescrever se já existir em excluídos (ou adicionar timestamp)
                    if os.path.exists(destino_path):
                        base, ext = os.path.splitext(filename_to_move)
                        destino_path = os.path.join(pasta_excluidos, f"{base}_{uuid.uuid4().hex[:8]}{ext}")

                    shutil.move(current_file_path, destino_path)
                    ficheiro_movido_nome = filename_to_move
                    current_app.logger.info(f"Ficheiro '{current_file_path}' movido para '{destino_path}'.")
                else:
                    current_app.logger.warning(f"Ficheiro local '{current_file_path}' correspondente à URI '{media_uri_to_remove_param}' não encontrado para mover.")
            else:
                 current_app.logger.warning(f"UPLOAD_FOLDER não configurado ou nome do ficheiro não pôde ser extraído da URI '{media_uri_to_remove_param}'.")
        else:
            current_app.logger.info(f"A URI '{media_uri_to_remove_param}' não parece ser de um ficheiro local gerido por este sistema. Apenas a relação RDF foi removida.")

        return jsonify({
            'message': 'Associação de mídia removida com sucesso.' + (' Ficheiro local movido para excluídos.' if ficheiro_movido_nome else ' Nenhum ficheiro local correspondente foi movido.'),
            'media_uri_removida': media_uri_to_remove_param,
            'ficheiro_movido': ficheiro_movido_nome
        }), 200

    except Exception as e: # Captura exceções gerais, incluindo as de execute_sparql_update
        current_app.logger.error(f"Erro geral no endpoint /remove: {str(e)}")
        if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[0], str) and "status" in e.args[0]:
            status_code = int(e.args[0].split("status ")[1].split(" ")[0])
            message = e.args[1]
            return jsonify({"error": "SPARQL Update Error", "message": message}), status_code
        elif "Network error" in str(e):
            return jsonify({"error": "Network Error", "message": str(e)}), 500
        else:
            return jsonify({'error': 'Erro interno no servidor ao remover mídia.', 'details': str(e)}), 500
