import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Lista de cidades que você quer consultar
cidades = ["Trindade,GO"]

prompt = f"""
Forneça a latitude, longitude, se é uma cidade, distrito, ou outro tipo,  o nome/título do lugar, e uma breve descrição se possível com informações de fundação (máximo 4 frases) para cada cidade/lugar:
{', '.join(cidades)}

Retorne no formato JSON estrito como uma lista de objetos contendo:
"lugar", "latitude", "longitude", "titulo" e "descricao".
"""

# Atualizado para gemini-3.6-flash
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    )
)

# Converte o texto da resposta para objeto Python (list/dict)
dados_cidades = json.loads(response.text)

# Imprime o JSON formatado
print(json.dumps(dados_cidades, indent=2, ensure_ascii=False))