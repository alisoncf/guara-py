from flask import Flask, jsonify, request
from rdflib import Graph, URIRef, Literal, RDF, OWL, RDFS
from rdflib.namespace import Namespace, NamespaceManager

app = Flask(__name__)

# Configuração do namespace da microontologia
cmgc = Namespace("http://www.guara.ueg.br/ontologias/v1/cmgclass#")

# Configuração do TDB
fuseki_url = "http://200.137.241.247:8080/fuseki/mplclasses"

# Função para carregar o grafo RDF


def load_rdf_graph():
    graph = Graph()
    graph.namespace_manager.bind("cmgc", cmgc)
    graph.parse(fuseki_url, format="turtle")
    return graph

# Endpoint para listar todas as classes do acervo


@app.route('/acervo/classes', methods=['GET'])
def listar_classes_acervo():
    graph = load_rdf_graph()
    query = """
        PREFIX cmgc: <http://www.guara.ueg.br/ontologias/v1/cmgclass#>
        SELECT ?classe ?label ?comentario ?classe_mae
        WHERE {
            ?classe rdf:type owl:Class ;
                    rdfs:label ?label ;
                    rdfs:comment ?comentario .
            OPTIONAL {
                ?classe rdfs:subClassOf ?classe_mae .
            }
            FILTER (?classe != cmgc:Acervo)
        }
    """
    results = graph.query(query)
    classes = []
    for result in results:
        classe_uri = result['classe']
        label = result['label']
        comentario = result['comentario']
        classe_mae = result['classe_mae'] if 'classe_mae' in result else None
        classes.append({
            'uri': classe_uri,
            'label': label,
            'comentario': comentario,
            'classe_mae': classe_mae
        })
    return jsonify(classes)

# Endpoint para adicionar uma nova classe ao acervo


@app.route('/acervo/classe', methods=['POST'])
def adicionar_classe_acervo():
    data = request.get_json()
    label = data.get('label')
    comentario = data.get('comentario')
    classe_mae_uri = data.get('classe_mae')

    graph = load_rdf_graph()

    # Gerando URI para a nova classe
    nova_classe_uri = cmgc[label.replace(" ", "_")]

    # Adicionando a nova classe ao grafo
    graph.add((nova_classe_uri, RDF.type, OWL.Class))
    graph.add((nova_classe_uri, RDFS.label, Literal(label)))
    graph.add((nova_classe_uri, RDFS.comment, Literal(comentario)))

    if classe_mae_uri:
        classe_mae_uri = URIRef(classe_mae_uri)
        graph.add((nova_classe_uri, RDFS.subClassOf, classe_mae_uri))

    # Enviando as alterações para o TDB
    graph.serialize(destination=fuseki_url, format='turtle')

    return jsonify({'message': 'Classe adicionada com sucesso'}), 201


# Execução do aplicativo Flask
if __name__ == '__main__':
    app.run(debug=True)
