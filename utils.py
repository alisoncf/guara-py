# guara/utils.py

import requests
from flask import current_app, jsonify
from urllib.parse import urlencode


def execute_sparql_query(endpoint_url, sparql_query):
    """
    Executa uma consulta SPARQL (SELECT, ASK) em um endpoint especificado usando GET.
    Este é o método padrão e mais compatível para queries.

    Args:
        endpoint_url (str): A URL do endpoint SPARQL de consulta.
        sparql_query (str): A string da consulta SPARQL.

    Returns:
        dict: O resultado da consulta em formato JSON.
        None: Se ocorrer um erro.
    """
    headers = {
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
    }
    # Para requisições GET, os parâmetros são passados via 'params'
    params = {'query': sparql_query}

    try:
        current_app.logger.debug(f"Executando SPARQL Query (GET) em {endpoint_url}")
        # AQUI ESTÁ A CORREÇÃO: trocado requests.post por requests.get
        response = requests.get(endpoint_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()  # Lança uma exceção para respostas 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na consulta SPARQL: {http_err} - Resposta: {response.text}")
        # Propaga a exceção com detalhes para ser tratada no blueprint
        raise Exception(f"SPARQL query failed with status {response.status_code}", response.text)
    except requests.exceptions.RequestException as req_err:
        current_app.logger.error(f"Erro de rede ao executar a consulta SPARQL: {req_err}")
        raise Exception(f"Network error executing SPARQL query: {req_err}")


def execute_sparql_update(endpoint_url, sparql_update):
    """
    Executa uma atualização SPARQL (INSERT, DELETE) em um endpoint especificado.
    Usa POST com Content-Type 'application/sparql-update', que é o padrão.

    Args:
        endpoint_url (str): A URL do endpoint SPARQL de atualização.
        sparql_update (str): A string da atualização SPARQL.

    Returns:
        bool: True se a atualização for bem-sucedida.

    Raises:
        Exception: Se ocorrer um erro durante a atualização.
    """
    headers = {
        'Accept': 'application/json,*/*;q=0.9',
        # AJUSTE: Usando o Content-Type padrão para updates, que é mais robusto.
        'Content-Type': 'application/sparql-update',
    }

    try:
        current_app.logger.debug(f"Executando SPARQL Update em {endpoint_url}: {sparql_update}")
        # A query de update é enviada diretamente no corpo da requisição com o encoding correto
        response = requests.post(endpoint_url, headers=headers, data=sparql_update.encode('utf-8'), timeout=15)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na atualização SPARQL: {http_err} - Resposta: {response.text}")
        raise Exception(f"SPARQL update failed with status {response.status_code}", response.text)
    except requests.exceptions.RequestException as req_err:
        current_app.logger.error(f"Erro de rede ao executar a atualização SPARQL: {req_err}")
        raise Exception(f"Network error executing SPARQL update: {req_err}")

def sparql_endpoint_works(endpoint_url):
    """
    Testa se o endpoint SPARQL aceita queries via POST.
    Retorna True se funcionar, False caso contrário.
    """
    test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
    headers = {'Accept': 'application/sparql-results+json'}
    try:
        response = requests.post(
            endpoint_url,
            data={'query': test_query},
            headers=headers,
            timeout=5
        )
        # Considere válido se retornar 200 ou 400 (erro de query, mas endpoint existe)
        return response.status_code in [200, 400]
    except Exception:
        return False