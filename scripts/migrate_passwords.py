"""Rehash senhas em texto puro (foaf:password) armazenadas na triplestore.

Uso:
    python scripts/migrate_passwords.py            # dry run, só lista quem seria alterado
    python scripts/migrate_passwords.py --apply    # efetivamente regrava os hashes
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests
from werkzeug.security import generate_password_hash

from app.config_loader import load_config

HASH_PREFIXES = ('scrypt:', 'pbkdf2:')


def sparql_escape(value):
    return (str(value)
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r'))


def fetch_users(query_url):
    query = """
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    SELECT ?s ?senha WHERE {
        ?s foaf:password ?senha .
    }
    """
    headers = {'Accept': 'application/sparql-results+json'}
    response = requests.get(query_url, params={'query': query}, headers=headers)
    response.raise_for_status()
    return response.json()['results']['bindings']


def update_password(update_url, user_uri, new_hash):
    update = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    DELETE {{ <{user_uri}> foaf:password ?old }}
    INSERT {{ <{user_uri}> foaf:password "{sparql_escape(new_hash)}" }}
    WHERE {{ <{user_uri}> foaf:password ?old }}
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
    }
    response = requests.post(update_url, headers=headers, data=urlencode({'update': update}))
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                         help='Efetivamente grava os hashes (sem essa flag, só mostra o que seria alterado)')
    args = parser.parse_args()

    config = load_config()
    query_url = config.get('user_query_url')
    update_url = config.get('user_update_url')
    print(f'Consultando usuários em: {query_url}')

    users = fetch_users(query_url)
    plaintext_users = [u for u in users if not u['senha']['value'].startswith(HASH_PREFIXES)]

    if not plaintext_users:
        print('Nenhuma senha em texto puro encontrada.')
        return

    for user in plaintext_users:
        uri = user['s']['value']
        if args.apply:
            new_hash = generate_password_hash(user['senha']['value'])
            update_password(update_url, uri, new_hash)
            print(f'[OK] {uri} -> senha migrada para hash')
        else:
            print(f'[dry-run] {uri} seria migrado (senha em texto puro detectada)')

    if not args.apply:
        print(f'\n{len(plaintext_users)} usuário(s) seriam migrados. Rode com --apply para efetivar.')
    else:
        print(f'\n{len(plaintext_users)} usuário(s) migrados com sucesso.')


if __name__ == '__main__':
    main()
