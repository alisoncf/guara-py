def get_prefix():
    return """ PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX cmg: <http://www.cmg.ueg.br/schema>
PREFIX obj: <http://200.137.241.247:8080/fuseki/objetos#>
PREFIX cls: <http://200.137.241.247:8080/fuseki/classes#>
PREFIX dim: <http://200.137.241.247:8080/fuseki/dimensoes#>
PREFIX owl: <http://www.w3.org/2002/07/owl#> """


def get_sparq_obj():
    return get_prefix() + """
SELECT DISTINCT ?obj  ?titulo ?resumo ?tipo
WHERE {
    ?obj a dim:ObjetoFisico.
    ?obj dc:title ?titulo.
    ?obj dc:subject ?resumo.
    ?obj rdfs:type ?tipo.
    FILTER (regex(?obj, '%keyword%', 'i')
            || regex(?titulo, '%keyword%', 'i')
            || regex(?resumo, '%keyword%', 'i'))}
            """


def get_sparq_class():
    return get_prefix() + """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?class ?label ?description ?subclassof
WHERE {
    ?class a owl:Class.
    OPTIONAL { ?class rdfs:label ?label }
    OPTIONAL { ?class rdfs:comment ?description }
    OPTIONAL { ?class rdfs:subClassOf ?subclassof }
    FILTER ((!bound(?description) || (regex(?description, "%keyword%", "i")))
            || (!bound(?label) || (regex(?label, "%keyword%", "i"))))
}ORDER BY asc(?%orderby%)"""
