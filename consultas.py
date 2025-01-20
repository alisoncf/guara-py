def get_prefix():
    return """ PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX obj: <http://200.137.241.247:8080/fuseki/objetos#>
PREFIX classdef: <http://200.137.241.247:8080/fuseki/classes#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX cmg: <http://www.cmg.ueg.br/schema>
PREFIX owl: <http://www.w3.org/2002/07/owl#> """


def get_sparq_obj():
    return get_prefix() + """
SELECT DISTINCT ?obj ?titulo ?resumo ?colecao (GROUP_CONCAT(DISTINCT ?tipo; SEPARATOR=", ") AS ?tipos)
WHERE {
    ?obj a obj:ObjetoFisico.
    ?obj dc:title ?titulo.
    ?obj dc:subject ?resumo.
    OPTIONAL { ?obj obj:colecao ?colecao. }
    OPTIONAL { ?obj obj:tipoFisico ?tipo. }
    FILTER (regex(?obj, '', 'i') || regex(?titulo, '', 'i') || regex(?resumo, '', 'i'))
}
GROUP BY ?obj ?titulo ?resumo ?colecao
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


def get_sparq_repo():
    return get_prefix() + """
prefix :     <http://200.137.241.247:8080/fuseki/repositoriosamigos#> 
prefix rpa:   <http://200.137.241.247:8080/fuseki/repositorios#> 
prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
prefix owl:   <http://www.w3.org/2002/07/owl#> 
prefix xsd:   <http://www.w3.org/2001/XMLSchema#> 
prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> 
SELECT ?nome ?uri ?contato ?descricao ?responsavel
WHERE {
  ?repo rpa:uri ?uri.
  ?repo rpa:nome ?nome.
  OPTIONAL { ?repo rpa:contato ?contato.}
  OPTIONAL { ?repo rpa:descricao ?descricao.}
  OPTIONAL { ?repo rpa:responsavel ?responsavel.}
}order by ?nome"""
