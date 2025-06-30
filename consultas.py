def get_base(): return """http://localhost:3030"""
def get_prefix():
    return """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX obj: <http://guara.ueg.br/ontologias/v1/objetos#>
PREFIX classdef: <http://guara.ueg.br/ontologias/v1/classes#>
PREFIX dc: <http://purl.org/dc/terms/>
PREFIX cmg: <http://www.cmg.ueg.br/schema>
PREFIX schema: <http://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rpa: <http://localhost:3030/repositorios#>
"""


def get_sparq_dim():
    return get_prefix() + """
    SELECT DISTINCT ?obj ?titulo ?resumo ?descricao ?dimensao ?lat ?lon
    WHERE {
        ?obj a ?dimensao .
        FILTER (?dimensao IN (obj:Pessoa, obj:Tempo, obj:Lugar, obj:Evento)).
        ?obj dc:title ?titulo.
        ?obj dc:abstract ?resumo.
        OPTIONAL { ?obj dc:description ?descricao . }
        OPTIONAL { ?obj obj:tipoFisico ?tipo. }
        OPTIONAL { ?obj geo:lat ?lat. }
        OPTIONAL { ?obj geo:lon ?lon. }
        FILTER (regex(?obj, '%keyword%', 'i') || regex(?titulo, '%keyword%', 'i') || regex(?resumo, '%keyword%', 'i'))
    }
    GROUP BY ?obj ?titulo ?resumo ?colecao ?descricao ?dimensao ?lat ?lon
    ORDER BY ?dimensao ?titulo
            """
def get_sparq_all():
    # CORREÇÃO: Adicionado "?colecao" no SELECT e no GROUP BY, e "OPTIONAL { ?id obj:colecao ?colecao. }" no WHERE.
    # Isso garante que a informação de qual coleção um objeto pertence seja retornada.
    return get_prefix() + """
SELECT ?id ?titulo ?descricao ?assunto ?tipo ?dimensao ?colecao (GROUP_CONCAT(STR(?tipoFisicoRaw); separator=", ") AS ?tipoFisico)
WHERE {
  ?id rdf:type ?tipoClasse ;
      dc:title ?titulo ;
      dc:description ?descricao ;
      %tipo%
      dc:abstract ?assunto .

  OPTIONAL { ?id obj:dimensao ?dimensaoRaw. }
  OPTIONAL { ?id obj:tipoFisico ?tipoFisicoRaw. }
  OPTIONAL { ?id obj:colecao ?colecao. }

  FILTER (
    ?tipoClasse = obj:ObjetoFisico || ?tipoClasse = obj:ObjetoDimensional
  )

  BIND(
    IF(?tipoClasse = obj:ObjetoFisico, "Físico", "Dimensional") AS ?tipo
  )

  BIND(
    IF(BOUND(?dimensaoRaw), STR(?dimensaoRaw), "") AS ?dimensao
  )

  FILTER (
    CONTAINS(LCASE(STR(?titulo)), LCASE("%keyword%")) ||
    CONTAINS(LCASE(STR(?descricao)), LCASE("%keyword%")) ||
    CONTAINS(LCASE(STR(?assunto)), LCASE("%keyword%"))
  )
}
GROUP BY ?id ?titulo ?descricao ?assunto ?tipo ?dimensao ?colecao
ORDER BY ?tipo ?titulo
            """

def get_sparq_obj():
    return get_prefix() + """
    SELECT DISTINCT ?obj ?titulo ?resumo ?descricao ?colecao (GROUP_CONCAT(DISTINCT ?tipo; SEPARATOR=", ") AS ?tipos)
    WHERE {
        ?obj a obj:ObjetoFisico.
        ?obj dc:title ?titulo.
        ?obj dc:abstract ?resumo.
        OPTIONAL { ?obj dc:description ?descricao . }
        OPTIONAL { ?obj obj:colecao ?colecao. }
        OPTIONAL { ?obj obj:tipoFisico ?tipo. }
        FILTER (regex(?obj, '%keyword%', 'i') || regex(?titulo, '%keyword%', 'i') || regex(?resumo, '%keyword%', 'i'))
    }
    GROUP BY ?obj ?titulo ?resumo ?colecao ?descricao
            """

def get_sparq_class():
    return get_prefix() + """
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
    consulta = """
SELECT ?nome ?uri ?contato ?descricao ?responsavel
WHERE {
  ?repo a rpa:Repositorio .
  ?repo rpa:uri ?uri.
  ?repo rpa:nome ?nome.
  OPTIONAL { ?repo rpa:contato ?contato. }
  OPTIONAL { ?repo rpa:descricao ?descricao. }
  OPTIONAL { ?repo rpa:responsavel ?responsavel. }
  %filter_aqui%
} ORDER BY ?nome
"""
    return get_prefix() + consulta
