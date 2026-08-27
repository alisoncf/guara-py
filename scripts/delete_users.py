"""Remove todos os usuários (curadores) da triplestore, exceto os informados em --keep.

Uso:
    python scripts/delete_users.py --keep alison                 # dry run
    python scripts/delete_users.py --keep alison --apply          # efetivamente apaga
    python scripts/delete_users.py --keep alison --keep outro_user --apply
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests

from app.config_loader import load_config


def fetch_users(query_url):
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX : <https://guara.ueg.br/fuseki/usuarios#>
    SELECT DISTINCT ?s ?username ?mbox WHERE {
        ?s rdf:type :Curador .
        OPTIONAL { ?s :username ?username }
        OPTIONAL { ?s foaf:mbox ?mbox }
    }
    """
    headers = {'Accept': 'application/sparql-results+json'}
    response = requests.get(query_url, params={'query': query}, headers=headers)
    response.raise_for_status()
    return response.json()['results']['bindings']


def delete_user(update_url, user_uri):
    update = f"""
    DELETE WHERE {{ <{user_uri}> ?p ?o }}
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
    }
    response = requests.post(update_url, headers=headers, data=urlencode({'update': update}))
    response.raise_for_status()


def local_name(uri):
    return uri.rsplit('#', 1)[-1].rsplit('/', 1)[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep', action='append', required=True,
                         help='username (nome local, ex: alison) a preservar. Pode repetir a flag para manter mais de um.')
    parser.add_argument('--apply', action='store_true',
                         help='Efetivamente apaga (sem essa flag, só mostra quem seria apagado)')
    args = parser.parse_args()
    keep = set(args.keep)

    config = load_config()
    query_url = config.get('user_query_url')
    update_url = config.get('user_update_url')
    print(f'Consultando usuários em: {query_url}')

    users = fetch_users(query_url)
    to_delete = [u for u in users if local_name(u['s']['value']) not in keep]

    if not to_delete:
        print('Nenhum usuário para apagar.')
        return

    for user in to_delete:
        uri = user['s']['value']
        username = user.get('username', {}).get('value', '?')
        mbox = user.get('mbox', {}).get('value', '?')
        if args.apply:
            delete_user(update_url, uri)
            print(f'[OK] apagado: {uri} (username={username}, mbox={mbox})')
        else:
            print(f'[dry-run] seria apagado: {uri} (username={username}, mbox={mbox})')

    if not args.apply:
        print(f'\n{len(to_delete)} usuário(s) seriam apagados. Rode com --apply para efetivar.')
    else:
        print(f'\n{len(to_delete)} usuário(s) apagados com sucesso.')


if __name__ == '__main__':
    main()
