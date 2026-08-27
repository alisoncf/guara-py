from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os, uuid, shutil, hashlib
from werkzeug.utils import secure_filename
from  ..blueprints.objectapi import add_relation

import requests
uploadapp = Blueprint('uploadapi', __name__)


def sha256_arquivo(caminho, chunk_size=8192):
    hasher = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_upload(file_storage, chunk_size=8192):
    hasher = hashlib.sha256()
    file_storage.stream.seek(0)
    for chunk in iter(lambda: file_storage.stream.read(chunk_size), b''):
        hasher.update(chunk)
    file_storage.stream.seek(0)
    return hasher.hexdigest()


@uploadapp.route('/midias/<objeto_id>/<filename>', methods=['GET'])
def get_midia(objeto_id, filename):
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    objeto_folder = os.path.join(upload_folder, secure_filename(str(objeto_id)))
    safe_filename = secure_filename(filename)

    if not os.path.isfile(os.path.join(objeto_folder, safe_filename)):
        return jsonify({'error': 'Arquivo não encontrado'}), 404

    return send_from_directory(objeto_folder, safe_filename)

@uploadapp.route('/upload', methods=['POST'])
def upload():
    # Obtém o ID do objeto a partir do formulário
    objeto_id = request.form.get('objetoId')
    repository = request.form.get('repository')
    links = request.form.getlist('links')
    arquivos = request.files.getlist('midias')    
    
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    objeto_folder = os.path.join(upload_folder, str(objeto_id))
    
    if not os.path.exists(objeto_folder):
        os.makedirs(objeto_folder)

    if not objeto_id:
        return jsonify({'error': 'ID do objeto não fornecido'}), 400



    # Verifica se arquivos foram enviados e se estão válidos (não vazios)
    arquivos_validos = [file for file in arquivos if file and file.filename.strip() != '']

    # Verifica se há ao menos um link ou ao menos um arquivo válido
    if not arquivos_validos and len(links) == 0:
        return jsonify({'error': 'Nenhuma mídia ou link enviado'}), 400

    # Verifica se todas as extensões são permitidas antes de salvar qualquer arquivo
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    for file in arquivos_validos:
        extensao = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if extensao not in allowed_extensions:
            return jsonify({
                'error': f'Extensão "{extensao}" não permitida para o arquivo "{file.filename}"',
                'extensoes_permitidas': sorted(allowed_extensions)
            }), 400

    # Verifica duplicidade de conteúdo dentro do mesmo objeto (ignora a subpasta "excluidos")
    hashes_existentes = {
        sha256_arquivo(os.path.join(objeto_folder, nome))
        for nome in os.listdir(objeto_folder)
        if os.path.isfile(os.path.join(objeto_folder, nome))
    }
    for file in arquivos_validos:
        file_hash = sha256_upload(file)
        if file_hash in hashes_existentes:
            return jsonify({
                'error': f'O arquivo "{file.filename}" é idêntico a um arquivo já existente nesse objeto'
            }), 409
        hashes_existentes.add(file_hash)

    arquivos_salvos = []

    if len(arquivos)>0:
        for file in arquivos:
            if file.filename:
                nome_original, extensao = os.path.splitext(file.filename)
                extensao = extensao.lower()
                prefixo = uuid.uuid4().hex[:8]

                filename = secure_filename(f"{prefixo}_{nome_original}{extensao}")
                file_path = os.path.join(objeto_folder, filename)
                       
                file.save(file_path)
                arquivos_salvos.append(filename)  # Armazena apenas o nome do arquivo
            
            
                objeto_uri = f":{objeto_id}"
                file_path_normalized = file_path.replace("\\", "/")
                midia_uri = f'"{file_path_normalized}"'
                print('midiaURI',midia_uri)
                repositorio_uri = "http://www.guara.ueg.br/repositorio"  
                propriedade = "schema:associatedMedia"
                            
                resultado = add_relation(midia_uri=midia_uri,
                                         objeto_uri=objeto_uri,
                                         propriedade=propriedade,
                                         repositorio_uri=repositorio_uri,
                                         repository=repository,
                                         )
                print('#resultado',resultado)
                
    if len(links)>0:
        for file in arquivos:
            objeto_uri = f":{objeto_id}"
            file_path_normalized = file_path.replace("\\", "/")
            midia_uri = f'"{file_path_normalized}"'
            print('midiaURI',midia_uri)
            repositorio_uri = "http://www.guara.ueg.br/repositorio"  
            propriedade = "schema:associatedMedia"
                        
            resultado = add_relation(midia_uri=midia_uri,
                                        objeto_uri=objeto_uri,
                                        propriedade=propriedade,
                                        repositorio_uri=repositorio_uri,
                                        repository=repository,
                                        )
            print('#resultado',resultado)
    return jsonify({
        'message': 'Mídias adicionadas!'
    }), 200
@uploadapp.route('/remove', methods=['POST'])
def remove_file():
    # Obtém o ID do objeto a partir do formulário
    data = request.get_json()
    objeto_id = data['objetoId']
    repository = data['repositorio']
    file_name = data['file']
    
    if not objeto_id:
        return jsonify({'error': 'ID do objeto não fornecido'}), 400

    
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    objeto_folder = os.path.join(upload_folder, str(objeto_id))
    pasta_excluidos = os.path.join(objeto_folder, "excluidos")
    
    if not os.path.exists(pasta_excluidos):
        os.makedirs(pasta_excluidos)


    destino_path = os.path.join(pasta_excluidos, file_name)

    if file_name:

        file_path = os.path.join(objeto_folder, file_name)
        #os.remove (file_path)
        try:
            shutil.move(file_path, destino_path)
        except:
            ()
        objeto_uri = f":{objeto_id}"
        file_path_normalized = file_path.replace("\\", "/")
        midia_uri = f'"{file_path_normalized}"'
        propriedade = "schema:associatedMedia"

        try:
            response = requests.delete(
                "http://localhost:5000/fis/remover_relacao",  # URL da rota `remover_relacao`
                json={
                    "s": objeto_uri,
                    "p": propriedade,
                    "o": midia_uri,
                    "repository": repository
                },
                headers={"Authorization": request.headers.get("Authorization", "")}
            )

            if response.status_code != 200:
                
                return jsonify("erro",response.text), response.status_code  # Retorna erro se falhar
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Erro ao chamar adicionar_relacao", "message": str (e)}), 500   
    
    return jsonify({
        'message': 'Arquivos excluído com sucesso!'
    }), 200