import json

def load_config(filename='config.json'):
    with open(filename, 'r') as f:
        return json.load(f)