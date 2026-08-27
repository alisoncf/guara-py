import json
import os

def load_config(filename='config.json'):
    # Constrói o caminho relativo ao diretório do módulo app
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, 'r') as f:
        raw = f.read()
    fuseki_base_url = os.getenv('FUSEKI_BASE_URL', 'http://localhost:3030')
    raw = raw.replace('{{FUSEKI_BASE_URL}}', fuseki_base_url)
    return json.loads(raw)
