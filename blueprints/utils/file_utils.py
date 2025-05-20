import os
import uuid
from werkzeug.utils import secure_filename

def salvar_arquivos(arquivos, objeto_id, upload_folder):
    """
    Salva os arquivos no diretório do objeto e retorna a lista de caminhos salvos.
    """
    objeto_folder = os.path.join(upload_folder, str(objeto_id))
    if not os.path.exists(objeto_folder):
        os.makedirs(objeto_folder)

    arquivos_salvos = []

    for file in arquivos:
        if file and file.filename.strip():
            extensao = os.path.splitext(file.filename)[-1]
            filename = secure_filename(f"{uuid.uuid4().hex}{extensao}")
            file_path = os.path.join(objeto_folder, filename)
            file.save(file_path)
            arquivos_salvos.append(file_path)

    return arquivos_salvos
