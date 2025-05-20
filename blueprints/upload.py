from flask import Blueprint, request, jsonify, current_app
import os, uuid, shutil
from werkzeug.utils import secure_filename
from  blueprints.objectapi import add_relation

import requests 
uploadapp = Blueprint('uploadapi', __name__)

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

    arquivos_salvos = []

    if len(arquivos)>0:
        for file in arquivos:
            if file.filename:
                extensao = os.path.split(".")[-1]
            
                filename = secure_filename(f"{uuid.uuid4().hex}{extensao}")
                file_path = os.path.join(objeto_folder, filename)
                       
                file.save(file_path)
                arquivos_salvos.append(filename)  # Armazena apenas o nome do arquivo
            
            
                objeto_uri = f":{objeto_id}"
                midia_uri = f'"{file_path.replace("\\", "/")}"'
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
            midia_uri = f'"{file_path.replace("\\", "/")}"'
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
        midia_uri = f":{file_name}"
        propriedade = "schema:associatedMedia"
        

        try:
            response = requests.delete(
                "http://localhost:5000/objectapi/remover_relacao",  # URL da rota `adicionar_relacao`
                json={
                    "s": objeto_uri,
                    "p": propriedade,
                    "o": midia_uri,
                    "repository": repository
                }
            )

            if response.status_code != 200:
                
                return jsonify("erro",response.text), response.status_code  # Retorna erro se falhar
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Erro ao chamar adicionar_relacao", "message": str (e)}), 500   
    
    return jsonify({
        'message': 'Arquivos excluído com sucesso!'
    }), 200