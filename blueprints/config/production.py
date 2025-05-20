from .base import BaseConfig

class ProductionConfig(BaseConfig):
    DEBUG = False
    SPARQL_ENDPOINT = 'http://guara.ueg.br/fuseki/'
