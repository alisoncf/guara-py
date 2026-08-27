import os

class BaseConfig:
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'changeme')
    SPARQL_ENDPOINT = 'http://localhost:3030/fuseki'  # padrão
    UPLOAD_FOLDER = '/var/www/imagens'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {
        'jpg', 'jpeg', 'png', 'gif', 'webp',
        'mp4', 'mov', 'avi', 'webm',
        'mp3', 'wav', 'ogg',
        'pdf', 'doc', 'docx', 'odt',
        'xls', 'xlsx', 'ppt', 'pptx', 'csv',
    }