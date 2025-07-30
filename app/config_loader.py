import json
import os

def load_config(filename='config.json'):
    # Constrói o caminho relativo ao diretório do módulo app
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, 'r') as f:
        return json.load(f)
