from flask import Blueprint, request, jsonify
import os
import json
from google import genai
from google.genai import types, errors
from ..blueprints.auth import token_required

iaapi_app = Blueprint('iaapi_app', __name__)

MAX_CIDADES_POR_REQUISICAO = 20
MAX_EVENTOS_POR_REQUISICAO = 20
MAX_PESSOAS_POR_REQUISICAO = 20

_client = None


def get_client():
    """Cria o client do Gemini de forma preguiçosa, só quando a rota é
    chamada — evita que a ausência de GEMINI_API_KEY quebre o import do
    blueprint (e, por consequência, o app inteiro) na inicialização."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY não configurada")
        _client = genai.Client(api_key=api_key)
    return _client


@iaapi_app.route('/cidades', methods=['POST'])
@token_required
def cidades():
    try:
        data = request.get_json()

        if not data or 'cidades' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'cidades' field"}), 400

        lista_cidades = data['cidades']

        if not isinstance(lista_cidades, list) or len(lista_cidades) == 0:
            return jsonify({"error": "Invalid input", "message": "'cidades' deve ser uma lista não vazia de strings"}), 400

        if len(lista_cidades) > MAX_CIDADES_POR_REQUISICAO:
            return jsonify({
                "error": "Invalid input",
                "message": f"Máximo de {MAX_CIDADES_POR_REQUISICAO} cidades por requisição"
            }), 400

        if not all(isinstance(c, str) and c.strip() for c in lista_cidades):
            return jsonify({"error": "Invalid input", "message": "Cada item de 'cidades' deve ser uma string não vazia"}), 400

        lista_cidades = [c.strip() for c in lista_cidades]

        prompt = f"""
Forneça a latitude, longitude, se é uma cidade, distrito, ou outro tipo, o nome/título do lugar, e uma breve descrição se possível com informações de fundação (máximo 4 frases) para cada cidade/lugar:
{', '.join(lista_cidades)}

Retorne no formato JSON estrito como uma lista de objetos contendo:
"lugar", "latitude", "longitude", "titulo" e "descricao".
"""

        response = get_client().models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        dados_cidades = json.loads(response.text)

        return jsonify({"cidades": dados_cidades}), 200

    except RuntimeError as e:
        print('#IA cidades - configuração ausente:', e)
        return jsonify({"error": "Configuração ausente", "message": "Serviço de IA não configurado"}), 503

    except errors.APIError as e:
        print('#IA cidades - erro da API do Gemini:', e)
        status = e.code if isinstance(e.code, int) and 400 <= e.code < 600 else 502
        return jsonify({"error": "Erro no serviço de IA", "message": e.message}), status

    except json.JSONDecodeError as e:
        print('#IA cidades - resposta inválida da IA:', e)
        return jsonify({"error": "Erro ao interpretar resposta da IA"}), 502

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        print('#IA cidades - erro:', e)
        return jsonify({"error": "Erro interno ao consultar cidades"}), 500


@iaapi_app.route('/eventos', methods=['POST'])
@token_required
def eventos():
    try:
        data = request.get_json()

        if not data or 'eventos' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'eventos' field"}), 400

        lista_eventos = data['eventos']

        if not isinstance(lista_eventos, list) or len(lista_eventos) == 0:
            return jsonify({"error": "Invalid input", "message": "'eventos' deve ser uma lista não vazia de strings"}), 400

        if len(lista_eventos) > MAX_EVENTOS_POR_REQUISICAO:
            return jsonify({
                "error": "Invalid input",
                "message": f"Máximo de {MAX_EVENTOS_POR_REQUISICAO} eventos por requisição"
            }), 400

        if not all(isinstance(e, str) and e.strip() for e in lista_eventos):
            return jsonify({"error": "Invalid input", "message": "Cada item de 'eventos' deve ser uma string não vazia"}), 400

        lista_eventos = [e.strip() for e in lista_eventos]

        prompt = f"""
Forneça informações sobre cada evento/festa popular a seguir:
{', '.join(lista_eventos)}

Para cada um, traga: o nome/título do evento, um resumo (máximo 2 frases), uma descrição
com o histórico de origem (máximo 6 frases), o local (cidade/município e estado), o local de
realização (o espaço específico onde acontece, ex. praça, igreja, rua principal — quando
souber), as atividades principais, o período em que acontece (dia do ano, semana ou mês,
o que for mais preciso) e, se houver, alguma personagem histórica importante ou santo/santa
associado ao evento.

Retorne no formato JSON estrito como uma lista de objetos contendo:
"evento", "titulo", "resumo", "descricao_historico", "local", "local_realizacao",
"atividades_principais", "periodo" e "personagem_ou_santo" (use null quando não souber ou
não se aplicar).
"""

        response = get_client().models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        dados_eventos = json.loads(response.text)

        return jsonify({"eventos": dados_eventos}), 200

    except RuntimeError as e:
        print('#IA eventos - configuração ausente:', e)
        return jsonify({"error": "Configuração ausente", "message": "Serviço de IA não configurado"}), 503

    except errors.APIError as e:
        print('#IA eventos - erro da API do Gemini:', e)
        status = e.code if isinstance(e.code, int) and 400 <= e.code < 600 else 502
        return jsonify({"error": "Erro no serviço de IA", "message": e.message}), status

    except json.JSONDecodeError as e:
        print('#IA eventos - resposta inválida da IA:', e)
        return jsonify({"error": "Erro ao interpretar resposta da IA"}), 502

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        print('#IA eventos - erro:', e)
        return jsonify({"error": "Erro interno ao consultar eventos"}), 500


@iaapi_app.route('/pessoas', methods=['POST'])
@token_required
def pessoas():
    try:
        data = request.get_json()

        if not data or 'pessoas' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'pessoas' field"}), 400

        lista_pessoas = data['pessoas']

        if not isinstance(lista_pessoas, list) or len(lista_pessoas) == 0:
            return jsonify({"error": "Invalid input", "message": "'pessoas' deve ser uma lista não vazia de strings"}), 400

        if len(lista_pessoas) > MAX_PESSOAS_POR_REQUISICAO:
            return jsonify({
                "error": "Invalid input",
                "message": f"Máximo de {MAX_PESSOAS_POR_REQUISICAO} pessoas por requisição"
            }), 400

        if not all(isinstance(p, str) and p.strip() for p in lista_pessoas):
            return jsonify({"error": "Invalid input", "message": "Cada item de 'pessoas' deve ser uma string não vazia"}), 400

        lista_pessoas = [p.strip() for p in lista_pessoas]

        prompt = f"""
Forneça informações sobre cada pessoa/personagem histórica a seguir, se ela puder ser
identificada com razoável confiança:
{', '.join(lista_pessoas)}

Para cada uma, traga: o nome completo, as alcunhas ou como é/era popularmente conhecida
(ex. "Dona Dica"), um resumo (máximo 2 frases), um histórico biográfico (máximo 6 frases,
incluindo época/período em que viveu ou atuou e local associado, quando souber), e se ela
está associada a algum evento, festa popular ou manifestação cultural conhecida — nesse
caso, liste os nomes desses eventos. Se a pessoa não puder ser identificada com confiança,
indique isso explicitamente em vez de inventar informação.

Retorne no formato JSON estrito como uma lista de objetos contendo:
"pessoa", "nome", "alcunhas", "resumo", "historico", "local", "periodo",
"eventos_associados" e "encontrada" (booleano — false quando não for possível identificar
a pessoa com confiança). Use null nos demais campos quando "encontrada" for false, e use
null também em campos individuais que não souber quando "encontrada" for true.
"""

        response = get_client().models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        dados_pessoas = json.loads(response.text)

        return jsonify({"pessoas": dados_pessoas}), 200

    except RuntimeError as e:
        print('#IA pessoas - configuração ausente:', e)
        return jsonify({"error": "Configuração ausente", "message": "Serviço de IA não configurado"}), 503

    except errors.APIError as e:
        print('#IA pessoas - erro da API do Gemini:', e)
        status = e.code if isinstance(e.code, int) and 400 <= e.code < 600 else 502
        return jsonify({"error": "Erro no serviço de IA", "message": e.message}), status

    except json.JSONDecodeError as e:
        print('#IA pessoas - resposta inválida da IA:', e)
        return jsonify({"error": "Erro ao interpretar resposta da IA"}), 502

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        print('#IA pessoas - erro:', e)
        return jsonify({"error": "Erro interno ao consultar pessoas"}), 500


