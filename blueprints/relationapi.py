from flask import Blueprint, request, jsonify,current_app
import requests, os
import uuid
# Importe suas funções corretamente
from consultas import get_sparq_all,get_sparq_dim, get_prefix
from config_loader import load_config
from urllib.parse import urlencode
from blueprints.auth import token_required
relationapi_app = Blueprint('relationapi_app', __name__)


@relationapi_app.route('/list', methods=['GET','POST'])
def list():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'keyword' field"}), 400
        if 'repository' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        if 'id' not in data:
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'id' "}), 400
        if data['repository']=='' :
            return jsonify({"error": 'Invalid input', "message": "Expected JSON with 'repository' "}), 400
        
        objectUri = data['id']
        keyword = data['keyword']
        repo = data['repository']
        type = data['type']
        
        prefix_base = repo  + "#"
        sparqapi_url = repo
        
        sparql_query = get_prefix() + f"""
                SELECT ?id ?propriedade ?valor  
                    (IF(isURI(?valor), "URI", "Literal") AS ?tipo_recurso)
                    ?titulo
                WHERE {{
                {{
                    # Relações diretas
                    ?id ?propriedade ?valor .
                    FILTER(?id = <{objectUri}>)
                }}
                UNION
                {{
                    # Relações inversas
                    ?valor ?propriedade ?id .
                    FILTER(?id = <{objectUri}>)
                    BIND("direta" AS ?direcao)
                }}
                OPTIONAL {{
                    ?valor dc:title ?titulo .
                    FILTER(isURI(?valor))
                    BIND("direta" AS ?direcao)
                }}
                }}
                """

        print('query',sparql_query) 
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)
        
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)
        

        if response.status_code == 200:
            result = response.json()
            return jsonify(result)
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error": "KeyError", "message": str(e)}), 400

    except TypeError as e:
        return jsonify({"error": "TypeError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500



@relationapi_app.route('/add', methods=['POST'])
@token_required
def add():
    try:
        data = request.get_json()
        required_fields = ['id', 'propriedade', 'valor','repository','tipo_recurso']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        repo = data['repository']
        complemento = data['complemento'] if 'complemento' in data else ''
        prefixo = data['prefixo'] if 'prefixo' in data else ''
        object_id = data['id']
        tipo=data['tipo_recurso']
        property = data['propriedade']
        valor = data['valor'] if complemento!='' else data['valor'] + complemento;
        if  str.lower(tipo) =='uri': 
           value=f"""<{valor}>"""
        else:
            value=f"""'{valor}'"""
        sparqapi_url = repo
                # Construção final da query SPARQL
        sparql_query = f"""{get_prefix()+ ' '+  prefixo}
            PREFIX : <{repo}#>
            INSERT DATA {{
                :{object_id} <{property}> {value} .
            }}"""

        print('->', sparql_query)  # Debugging
        # Enviar a query SPARQL para o endpoint de atualização
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto digital adicionado com sucesso", "id": object_id}), 200
        else:
            print (response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500



@relationapi_app.route('/delete', methods=['DELETE','POST'])
@token_required
def remove():
    try:
        data = request.get_json()

        if "id" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' and 'repository' fields"}), 400
        
        repo = data["repository"]
        objeto_id = data["id"]
        #print(objeto_id)
        objeto_uri = f":{objeto_id}"
        sparqapi_url = f"{repo}/{load_config().get('update')}"
        
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE WHERE {{
                {objeto_uri} ?p ?o .
            }}
        """
        #print (sparql_query)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }

        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto físico excluído com sucesso", "id": objeto_id}), 200
        else:
            #print(response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
    
@relationapi_app.route('/remover_relacao', methods=['DELETE'])
@token_required
def remover_relacao():
    try:
        data = request.get_json()

        if "s" not in data or "p" not in data or "o" not in data or "repository" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 's','p','o' and 'repository' fields"}), 400
        
        repo = data["repository"]
        
        s = data["s"]
        p = data["p"]
        o = data["s"]
        
        
        sparqapi_url = f"{repo}/{load_config().get('update')}"
        
        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE WHERE {{
                {s} {p} {o} .
            }}
        """
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/sparql-results+json,*/*;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        }

        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "relação excluído com sucessa", "id": '{s} {p} {o}'}), 200
        else:
            #print(response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
    
@relationapi_app.route('/update', methods=['PUT','POST'])
@token_required
def update():
    try:
        data = request.get_json()
        
        if "id" not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'id' field"}), 400

        required_fields = ['descricao', 'titulo', 'resumo','id','repository','tipo']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": "Invalid input", "message": f"Expected JSON with '{field}' field"}), 400
        
        repo = data['repository']
        description=data['descricao']
        subject=data['resumo']
        titulo=data['titulo']
        object_id = data['id']
        objeto_uri = f":{object_id}"
        sparqapi_url = repo+'/'+load_config().get('update')
        
        

        sparql_query = f"""{get_prefix()}
            PREFIX : <{repo}#>
            DELETE {{
                {objeto_uri} dc:description ?oldDescription; dc:title ?oldTitle ;
                dc:subject ?oldSubject.
            }}
            INSERT {{
                {objeto_uri} 
                    dc:description "{description}";
                    dc:subject "{subject}";
                    dc:title "{titulo}" .
            }}
            WHERE {{
                {objeto_uri}  dc:title ?oldTitle ;
                dc:description ?oldDescription ;
                dc:subject ?oldSubject.
            }}
        """
        print('update',sparql_query)   
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/sparql-results+json,*/*;q=0.9',
                'X-Requested-With': 'XMLHttpRequest'}
        data = {'update': sparql_query}
        encoded_data = urlencode(data)
         
        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto atualizado com sucesso", "id": object_id}), 200
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code

        #return jsonify({"message": "Nenhuma alteração enviada"}), 400

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500
    

@relationapi_app.route('/add_relation', methods=['POST'])
@token_required
def add_relation():
    try:
        data = request.get_json()
        objeto = data["o"]
        repositorio = data["repositorio_uri"]
        midia = data["midia_uri"]
        propriedade = data["propriedade"]
        repo = data['repository']
        sparqapi_url = repo+'/'+load_config().get('update')
        sparql_query = f"""{get_prefix()}
        PREFIX : <{repo}#>
        INSERT DATA {{
        {objeto} {propriedade} {midia} .
        }}
        """
        #print('add relação:',sparql_query, ' no repositório ', sparqapi_url)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With': 'XMLHttpRequest'}
        data = {'update': sparql_query}
        encoded_data = urlencode(data)

        response = requests.post(
            sparqapi_url, headers=headers, data=encoded_data)

        if response.status_code == 200:
            return jsonify({"message": "Objeto digital adicionado com sucesso", "id": objeto}), 200
        else:
            #print (response.text)
            return jsonify({"error1": response.status_code, "message": response.text}), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error2": "RequestException", "message": str(e)}), 500

    except KeyError as e:
        return jsonify({"error3": "KeyError", "message": str(e)}), 400

    except Exception as e:
        return jsonify({"error4": "Exception", "message": str(e)}), 500
