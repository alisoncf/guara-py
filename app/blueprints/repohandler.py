from flask import Blueprint, request, jsonify
import requests
from app.consultas import get_sparq_repo, get_prefix
from app.config_loader import load_config
from urllib.parse import urlencode
from app.config_loader import load_config
from auth import token_required 
from utils.file_utils import salvar_arquivos
from werkzeug.utils import secure_filename

import os, uuid
repo_handler = Blueprint('repo_handler', __name__)





@token_required
@repo_handler.route('/create', methods=['POST'])
def create():
    try:
        data = request.get_json()

        # Validar os campos obrigatórios
        required_fields = ['uri', 'nome','contato','descricao','responsavel']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        

        prefix_base = load_config().get('prefix_base_repo')
        repo_uri=prefix_base+data['uri']
        sparqapi_url = load_config().get('class_update_url')
        
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            prefix :      <{repo_uri}#> 
            prefix rpa:   <http://guara.ueg.br/ontologias/v1/repositorios#> 
            prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
            prefix owl:   <http://www.w3.org/2002/07/owl#> 
            prefix xsd:   <http://www.w3.org/2001/XMLSchema#> 
            prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
            
            INSERT DATA {{
                <{repo_uri}> rdf:type owl:Class ;
                                rpa:uri "{data['uri']}" ;
                                rpa:nome "{data['nome']}" ;
                                rpa:contato "{data['contato']}" ;
                                rpa:descricao "{data['descricao']}" ;
                                rpa:responsavel "{data['responsavel']}" .
            }}
        """
        #print('uri', repo_uri)
        #print('q', sparql_query)

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Classe adicionada com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@token_required
@repo_handler.route('/update', methods=['POST','PUT'])
def update():
    try:
        data = request.get_json()
    
        
        required_fields = ['uri', 'nome','contato','descricao','responsavel']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400

        
        arquivos = request.files.getlist('imagem') 

        if len(arquivos)>0:
            for file in arquivos:
                if file.filename:
                    extensao = os.path.split(".")[-1]
                
                    filename = secure_filename(f"{uuid.uuid4().hex}{extensao}")
                    file_path = os.path.join(objeto_folder, filename)
                    file.save(file_path)
                    arquivos_salvos.append(filename)


        prefix_base = load_config().get('prefix_base_repo')
        repo_uri=prefix_base+data['uri']
        sparqapi_url = load_config().get('class_update_url')
        
        # Montagem da query SPARQL de inserção
        sparql_query = f"""
            prefix :      <{repo_uri}#> 
            prefix rpa:   <http://guara.ueg.br/ontology/v1/repositorios#> 
            prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
            prefix owl:   <http://www.w3.org/2002/07/owl#> 
            prefix xsd:   <http://www.w3.org/2001/XMLSchema#> 
            prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
            prefix schema: <http://schema.org/>
            
            INSERT DATA {{
                <{repo_uri}> rdf:type owl:Class ;
                                rpa:uri "{data['uri']}" ;
                                rpa:nome "{data['nome']}" ;
                                rpa:contato "{data['contato']}" ;
                                rpa:descricao "{data['descricao']}" ;
                                rpa:responsavel "{data['responsavel']}" ;
                                schema:associatedMedia "{data['imagem']}" .
            }}
        """
        #print('uri', repo_uri)
        #print('q', sparql_query)

        # Preparação dos headers e dados para a requisição POST
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }
        data_envio = {'update': sparql_query}
        encoded_data = urlencode(data_envio)

        # Enviar a query SPARQL para o endpoint de atualização
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Classe adicionada com sucesso", "id": data['label']}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

