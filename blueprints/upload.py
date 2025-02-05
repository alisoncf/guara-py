from flask import Blueprint, request, jsonify, current_app
import os, uuid
from werkzeug.utils import secure_filename

uploadapp = Blueprint('uploadapp', __name__)

@uploadapp.route('/upload', methods=['POST'])
def upload_files():
    # Obtém o ID do objeto a partir do formulário
    objeto_id = request.form.get('objetoId')
    if not objeto_id:
        return jsonify({'error': 'ID do objeto não fornecido'}), 400


    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    objeto_folder = os.path.join(upload_folder, str(objeto_id))

    if not os.path.exists(objeto_folder):
        os.makedirs(objeto_folder)

    if 'midias' not in request.files:
        return jsonify({'error': 'Nenhuma mídia enviada'}), 400

    arquivos = request.files.getlist('midias')
  
    if not arquivos or all(file.filename == '' for file in arquivos):
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    arquivos_salvos = []

    # Processa cada arquivo
    for file in arquivos:
        if file.filename:
            # Gera um nome seguro para o arquivo
            extensao = os.path.splitext(file.filename)
            filename = secure_filename(f"{uuid.uuid4().hex}{extensao}")
            file_path = os.path.join(objeto_folder, filename)

            # Salva o arquivo no servidor
            file.save(file_path)
            arquivos_salvos.append(filename)  # Armazena apenas o nome do arquivo

    return jsonify({
        'message': 'Arquivos enviados com sucesso!',
        'arquivos': arquivos_salvos  # Retorna a lista de nomes dos arquivos salvos
    }), 200