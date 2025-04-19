def get_base(): return """http://localhost:3030"""
def get_prefix():
    return """ PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX obj: <http://guara.ueg.br/ontologias/v1/objetos#>
PREFIX classdef: <http://guara.ueg.br/ontologias/v1/classes#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX cmg: <http://www.cmg.ueg.br/schema>
PREFIX schema: <http://schema.org/>
PREFIX owl: <http://www.w3.org/2002/07/owl#> """


def get_sparq_dim():
    return get_prefix() + """
    SELECT DISTINCT ?obj ?titulo ?resumo ?descricao ?dimensao 
    WHERE {
        ?obj a ?dimensao .
        FILTER (?dimensao IN (obj:Pessoa, obj:Tempo, obj:Lugar, obj:Evento)).
        ?obj dc:title ?titulo.
        ?obj dc:subject ?resumo.
        OPTIONAL { ?obj dc:description ?descricao . }
        OPTIONAL { ?obj obj:tipoFisico ?tipo. }
        FILTER (regex(?obj, '%keyword%', 'i') || regex(?titulo, '%keyword%', 'i') || regex(?resumo, '%keyword%', 'i'))
    }
    GROUP BY ?obj ?titulo ?resumo ?colecao ?descricao ?dimensao
            """

def get_sparq_obj():
    return get_prefix() + """
    SELECT DISTINCT ?obj ?titulo ?resumo ?descricao ?colecao (GROUP_CONCAT(DISTINCT ?tipo; SEPARATOR=", ") AS ?tipos)
    WHERE {
        ?obj a obj:ObjetoFisico.
        ?obj dc:title ?titulo.
        ?obj dc:subject ?resumo.
        OPTIONAL { ?obj dc:description ?descricao . }
        OPTIONAL { ?obj obj:colecao ?colecao. }
        OPTIONAL { ?obj obj:tipoFisico ?tipo. }
        FILTER (regex(?obj, '%keyword%', 'i') || regex(?titulo, '%keyword%', 'i') || regex(?resumo, '%keyword%', 'i'))
    }
    GROUP BY ?obj ?titulo ?resumo ?colecao ?descricao
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
    base = get_base()
    prefixos = get_prefix()  # já vem formatado se você corrigiu como na resposta anterior
    consulta = f"""
PREFIX :     <{base}/repositoriosamigos#> 
PREFIX rpa:  <{base}/repositorios#> 
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX owl:  <http://www.w3.org/2002/07/owl#> 
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 

SELECT ?nome ?uri ?contato ?descricao ?responsavel
WHERE {{
  ?repo rpa:uri ?uri.
  ?repo rpa:nome ?nome.
  OPTIONAL {{ ?repo rpa:contato ?contato. }}
  OPTIONAL {{ ?repo rpa:descricao ?descricao. }}
  OPTIONAL {{ ?repo rpa:responsavel ?responsavel. }}
}} ORDER BY ?nome
"""
    retorno = prefixos + "\n" + consulta
    print('retorno', retorno)
    return retorno

    