# guara/utils.py

import requests
from flask import current_app, jsonify
from urllib.parse import urlencode


def execute_sparql_query(endpoint_url, sparql_query):
    """
    Executa uma consulta SPARQL (SELECT, ASK) em um endpoint especificado.

    Args:
        endpoint_url (str): A URL do endpoint SPARQL de consulta.
        sparql_query (str): A string da consulta SPARQL.

    Returns:
        dict: O resultado da consulta em formato JSON.
        None: Se ocorrer um erro.
    """
    headers = {
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
    }
    payload = {'query': sparql_query}
    encoded_data = urlencode(payload)

    try:
        current_app.logger.debug(f"Executando SPARQL Query em {endpoint_url}: {sparql_query}")
        response = requests.post(endpoint_url, headers=headers, data=encoded_data, timeout=15)
        response.raise_for_status()  # Lança uma exceção para respostas 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na consulta SPARQL: {http_err} - Resposta: {response.text}")
        # Retorna um objeto de erro que pode ser usado para construir uma resposta JSON
        raise Exception(f"SPARQL query failed with status {response.status_code}", response.text)
    except requests.exceptions.RequestException as req_err:
        current_app.logger.error(f"Erro de rede ao executar a consulta SPARQL: {req_err}")
        raise Exception(f"Network error executing SPARQL query: {req_err}")


def execute_sparql_update(endpoint_url, sparql_update):
    """
    Executa uma atualização SPARQL (INSERT, DELETE) em um endpoint especificado.

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
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
    }
    payload = {'update': sparql_update}
    encoded_data = urlencode(payload)

    try:
        current_app.logger.debug(f"Executando SPARQL Update em {endpoint_url}: {sparql_update}")
        response = requests.post(endpoint_url, headers=headers, data=encoded_data, timeout=15)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"Erro HTTP na atualização SPARQL: {http_err} - Resposta: {response.text}")
        raise Exception(f"SPARQL update failed with status {response.status_code}", response.text)
    except requests.exceptions.RequestException as req_err:
        current_app.logger.error(f"Erro de rede ao executar a atualização SPARQL: {req_err}")
        raise Exception(f"Network error executing SPARQL update: {req_err}")
