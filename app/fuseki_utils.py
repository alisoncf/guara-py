import os


def resolve_fuseki_endpoint(repo_uri):
    """Converte o URI público/identificador de um repositório (ex.:
    https://guara.ueg.br/fuseki/festas_populares) no endpoint HTTP
    interno real usado para consultar o Fuseki (ex.:
    http://host.docker.internal:3030/fuseki/festas_populares).

    O front-end e os dados gravados usam o URI público como IDENTIDADE
    do repositório (é o que aparece no navegador, o que foi gravado como
    rpa:uri). Mas o backend, rodando dentro de um container Docker, não
    consegue fazer requisições HTTP de volta para esse endereço público
    (nem deveria - agora ele nem é mais acessível de fora). Por isso,
    sempre que for de fato *conectar* no Fuseki, usamos o endpoint
    interno (FUSEKI_BASE_URL), preservando o restante do caminho.
    """
    public_base = "https://guara.ueg.br/fuseki"
    internal_base = os.getenv("FUSEKI_BASE_URL", "http://host.docker.internal:3030")

    if repo_uri and repo_uri.startswith(public_base):
        return internal_base + repo_uri[len(public_base):]

    return repo_uri