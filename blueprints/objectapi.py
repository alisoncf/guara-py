from flask import Blueprint, request, jsonify
import requests
from consultas import get_sparq_obj, get_sparq_class  # Importe suas funções corretamente
from config_loader import load_config
from urllib.parse import urlencode
objectapi_app = Blueprint('objectapi_app', __name__)

@objectapi_app.route('/listar_objetos', methods=['POST'])
def listar_objetos_fisicos():
    try:
        data = request.get_json()
        if 'keyword' not in data:
            return jsonify({"error": "Invalid input", "message": "Expected JSON with 'keyword' field"}), 400
        
        keyword = data['keyword']
        sparqapi_url = load_config().get('object_query_url')
        sparql_query = get_sparq_obj().replace('%keyword%', keyword)
        print(sparql_query)
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                   'Accept': 'application/sparql-results+json,*/*;q=0.9',
                   'X-Requested-With':'XMLHttpRequest'}
        data = {'query': sparql_query}
        encoded_data = urlencode(data)
        print('data->',encoded_data)
        response = requests.post(sparqapi_url, headers=headers,data=encoded_data)
        print ('response: ',response)

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
