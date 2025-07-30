from flask import Blueprint, request, jsonify
from kraken import binarization, pageseg, rpred
from PIL import Image
from pdf2image import convert_from_bytes
import io

bp_transcricao = Blueprint('transcricao', __name__)

@bp_transcricao.route('/api/transcricao', methods=['POST'])
def transcrever():
    if 'arquivo' not in request.files:
        return jsonify({'erro': 'Envie um arquivo PDF ou imagem com a chave "arquivo".'}), 400

    arquivo = request.files['arquivo']
    nome = arquivo.filename.lower()

    resultados = []

    try:
        if nome.endswith('.pdf'):
            paginas = convert_from_bytes(arquivo.read())
        else:
            paginas = [Image.open(arquivo.stream)]

        for i, img in enumerate(paginas):
            bin_img = binarization.nlbin(img)
            linhas = pageseg.segment(bin_img)
            predicoes = rpred.rpred(model='default', im=bin_img, bounds=linhas)
            texto = '\n'.join([line.prediction for line in predicoes])
            resultados.append({'pagina': i + 1, 'texto': texto})

        return jsonify({'transcricoes': resultados})

    except Exception as e:
        return jsonify({'erro': str(e)}), 500
