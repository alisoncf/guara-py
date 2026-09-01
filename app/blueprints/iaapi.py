from flask import Blueprint, request, jsonify
import os
import json
from google import genai
from google.genai import types, errors
from ..blueprints.auth import token_required

iaapi_app = Blueprint('iaapi_app', __name__)

MAX_CIDADES_POR_REQUISICAO = 20

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
