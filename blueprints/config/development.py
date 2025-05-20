from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SPARQL_ENDPOINT = 'http://localhost:3030/'
