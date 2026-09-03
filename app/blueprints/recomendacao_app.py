"""
Blueprint: recomendação semântica (módulo BERTimbau) para o Guará
=====================================================================

Expõe POST /recomendacao/sugerir — dado um objeto (novo ou existente, por
título + descrição), devolve sugestões de ligação (:quem/:oque/:onde/:quando)
com objetos dimensionais já existentes no acervo, rankeadas por similaridade
semântica via embeddings BERTimbau.

Reaproveita:
  - recomendacao_semantica.py  (ModeloEmbeddings, sugerir_ligacoes_para_novo_objeto)
  - sparql_escape.py           (validação de URI do parâmetro 'repository')

Formato de resposta pensado para uso direto pelo ComponenteRelacao.vue: cada
sugestão já vem com a URI completa da propriedade (:quem/:oque/:onde/:quando)
e o id extraído (mesmo padrão de STRAFTER que vocês já usam na rota /list),
prontos para montar a Tripla e chamar addRelacao() sem transformação extra
no frontend.

Registro no app Flask (segue o mesmo padrão dos outros blueprints):
    from .blueprints.recomendacao_app import recomendacao_app
    app.register_blueprint(recomendacao_app, url_prefix='/recomendacao')
"""

import logging
import threading

import pandas as pd
from flask import Blueprint, request, jsonify

from ..consultas import get_prefix
from ..blueprints.auth import token_required
from .sparql_escape import validar_uri_sparql
from ..recomendacao_semantica import (
    ModeloEmbeddings,
    gerar_embeddings,
    sugerir_ligacoes_para_novo_objeto,
)

import requests
from urllib.parse import urlencode

logger = logging.getLogger(__name__)
recomendacao_app = Blueprint('recomendacao_app', __name__)

# --- Cache do modelo em memória (processo) ------------------------------
# Carregar o BERTimbau é caro (baixa/inicializa pesos uma vez); NÃO fazer
# isso a cada requisição. Um lock evita duas requisições simultâneas
# disparando o carregamento em paralelo na primeira chamada.
_modelo_lock = threading.Lock()
_modelo_cache: ModeloEmbeddings | None = None


def _obter_modelo() -> ModeloEmbeddings:
    global _modelo_cache
    if _modelo_cache is None:
        with _modelo_lock:
            if _modelo_cache is None:  # dupla checagem dentro do lock
                logger.info("Carregando BERTimbau pela primeira vez neste processo...")
                _modelo_cache = ModeloEmbeddings().carregar()
                logger.info("BERTimbau carregado e em cache.")
    return _modelo_cache


# Propriedades dimensionais válidas como alvo de sugestão — mesmo mapeamento
# usado em recomendacao_semantica.DIMENSAO_POR_TIPO, mas aqui já como URI
# completa (o que o frontend precisa para montar a Tripla).
_BASE_ONTOLOGIA = "http://guara.ueg.br/ontologias/v1/objetos#"
_PROPRIEDADE_POR_DIMENSAO = {
    "Pessoa": _BASE_ONTOLOGIA + "quem",
    "Evento": _BASE_ONTOLOGIA + "oque",
    "Lugar": _BASE_ONTOLOGIA + "onde",
    "Tempo": _BASE_ONTOLOGIA + "quando",
}


def _extrair_acervo_dimensional(repo: str) -> pd.DataFrame:
    """Busca só os objetos DIMENSIONAIS do acervo (candidatos válidos a
    :quem/:oque/:onde/:quando) — objetos físicos não entram aqui, pois não
    são alvo válido dessas quatro propriedades.
    """
    sparql_query = get_prefix() + f"""
        SELECT ?id ?titulo ?descricao ?tipoDimensao
        WHERE {{
            ?id obj:dimensao ?tipoDimensao .
            ?id dc:title ?titulo .
            OPTIONAL {{
                {{ ?id dc:description ?descricao }}
                UNION
                {{ ?id dc:abstract ?descricao }}
            }}
        }}
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
    }
    encoded = urlencode({'query': sparql_query})
    response = requests.post(repo, headers=headers, data=encoded)
    response.raise_for_status()
    resultado = response.json()

    linhas = []
    for b in resultado["results"]["bindings"]:
        tipo_uri = b.get("tipoDimensao", {}).get("value", "")
        # tipoDimensao vem como URI completa (ex. .../objetos#Pessoa) —
        # extrai só o nome da classe pro filtro por dimensão funcionar.
        tipo_nome = tipo_uri.rsplit("#", 1)[-1] if "#" in tipo_uri else tipo_uri
        linhas.append({
            "objeto_uri": b["id"]["value"],
            "tipo": tipo_nome,
            "titulo": b.get("titulo", {}).get("value", ""),
            "descricao": b.get("descricao", {}).get("value", ""),
        })

    df = pd.DataFrame(linhas, columns=["objeto_uri", "tipo", "titulo", "descricao"])
    if not df.empty:
        df["texto"] = (df["titulo"].fillna("") + ". " + df["descricao"].fillna("")).str.strip()
    return df


@recomendacao_app.route('/sugerir', methods=['POST'])
@token_required
def sugerir():
    try:
        data = request.get_json()
        for campo in ('titulo', 'descricao', 'repository'):
            if campo not in data or data[campo] in (None, ''):
                return jsonify({
                    "error": "Invalid input",
                    "message": f"Expected JSON with '{campo}' field",
                }), 400

        repo = validar_uri_sparql(data['repository'])
        titulo = data['titulo']
        descricao = data['descricao']
        # 'id' é opcional: só vem preenchido quando o objeto já existe
        # (edição). Usado para EXCLUIR o próprio objeto do acervo antes de
        # gerar sugestões — sem isso, um objeto já cadastrado se compara
        # com o próprio texto e aparece como sugestão de si mesmo (100%
        # de similaridade sempre, o que não é útil nem faz sentido).
        objeto_id_proprio = data.get('id', '') or ''
        top_k = int(data.get('top_k_por_dimensao', 3))
        limiar = float(data.get('limiar', 0.4))

        texto_objeto = f"{titulo}. {descricao}".strip()

        df_acervo = _extrair_acervo_dimensional(repo)
        if df_acervo.empty:
            return jsonify({"sugestoes": [], "aviso": "Acervo dimensional vazio."}), 200

        if objeto_id_proprio:
            # 'objeto_id_proprio' pode chegar como URI completa ou só o
            # sufixo (UUID) — cobre os dois casos comparando pelo final da
            # URI de cada linha do acervo.
            sufixo_proprio = objeto_id_proprio.rsplit("#", 1)[-1]
            df_acervo = df_acervo[
                ~df_acervo["objeto_uri"].str.rsplit("#", n=1).str[-1].eq(sufixo_proprio)
            ].reset_index(drop=True)

        if df_acervo.empty:
            return jsonify({"sugestoes": [], "aviso": "Nenhum outro objeto no acervo para comparar."}), 200

        modelo = _obter_modelo()
        embeddings_acervo = gerar_embeddings(df_acervo, modelo=modelo)

        sugestoes_df = sugerir_ligacoes_para_novo_objeto(
            texto_objeto, df_acervo, embeddings_acervo,
            modelo=modelo, top_k_por_dimensao=top_k, limiar=limiar,
        )

        sugestoes = []
        for _, linha in sugestoes_df.iterrows():
            uri_recurso = linha["objeto_uri"]
            id_associado = uri_recurso.rsplit("#", 1)[-1] if "#" in uri_recurso else uri_recurso
            sugestoes.append({
                "dimensao": linha["dimensao"],
                "propriedade": _PROPRIEDADE_POR_DIMENSAO[linha["dimensao"]],
                "uri_recurso": uri_recurso,
                "id_associado": id_associado,
                "titulo_recurso": linha["titulo"],
                "similaridade": linha["similaridade"],
            })

        return jsonify({"sugestoes": sugestoes}), 200

    except ValueError as e:
        return jsonify({"error": "ValueError", "message": str(e)}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500
    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400
    except Exception as e:
        logger.exception("Erro inesperado em /recomendacao/sugerir")
        return jsonify({"error": "Exception", "message": str(e)}), 500
