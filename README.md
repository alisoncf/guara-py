Guará-Py API
Sobre o Projeto
Guará-Py é o serviço de backend para o Projeto Guará, uma plataforma de software para a gestão de acervos digitais utilizando tecnologias da Web Semântica.

Construído com Flask, este backend fornece uma API RESTful para interagir com um triplestore Apache Fuseki, permitindo a manipulação de dados descritos em ontologias (OWL) e RDF. A API gerencia objetos digitais, suas classificações, metadados e relações, além de controlar o acesso de usuários e o upload de mídias.

Recursos Principais
API RESTful Modular: Funcionalidades organizadas em Blueprints para fácil manutenção.

Integração com Web Semântica: Operações CRUD sobre dados RDF através de consultas SPARQL.

Gerenciamento de Ontologias: Endpoints para manipular classes e propriedades das ontologias.

Autenticação por Token: Sistema de login que fornece tokens JWT para proteger endpoints.

Upload de Mídia: Funcionalidade para upload de arquivos e associação semântica com os objetos do acervo.

Documentação Automática: Interface Swagger (via Flasgger) para documentação interativa da API.

Pré-requisitos
Antes de começar, você precisará ter instalado em sua máquina:

Python 3.9+

Pip (gerenciador de pacotes do Python)

Apache Fuseki: Um servidor SPARQL em execução. A API precisa se conectar a ele para funcionar.

Instalação e Configuração
Siga os passos abaixo para configurar o ambiente de desenvolvimento.

1. Clonar o Repositório

Bash

git clone <URL_DO_SEU_REPOSITORIO>
cd guara-py
2. Criar um Ambiente Virtual

É uma forte recomendação usar um ambiente virtual para isolar as dependências do projeto.

Windows:

Bash

python -m venv venv
.\venv\Scripts\activate
Linux / macOS:

Bash

python3 -m venv venv
source venv/bin/activate
3. Instalar as Dependências

Crie um arquivo chamado requirements.txt na raiz do projeto com o seguinte conteúdo:

Plaintext

# requirements.txt
Flask
Flask-Cors
flasgger
requests
python-dotenv
werkzeug
Em seguida, instale as dependências:

Bash

pip install -r requirements.txt
4. Configurar o Apache Fuseki

Certifique-se de que seu servidor Apache Fuseki esteja em execução. Você precisará criar os datasets que serão utilizados pela API. Os nomes dos datasets devem corresponder aos que estão no seu arquivo config.json. Por exemplo: usuarios, repositoriosamigos, mplobj, etc.

5. Configurar a Aplicação

Existem dois arquivos principais de configuração:

.env: Para variáveis de ambiente. Renomeie ou crie um arquivo .env a partir do exemplo abaixo:

Snippet de código

# .env
FLASK_ENV=development
UPLOAD_FOLDER=/caminho/para/sua/pasta/de/uploads
MEDIA_BASE_URL=/media

# Para produção com HTTPS (opcional)
# USE_SSL=true
# SSL_CERT_PATH=/caminho/para/certificado/cert.pem
# SSL_KEY_PATH=/caminho/para/certificado/key.pem
FLASK_ENV: Define o ambiente (development para depuração, production para produção).

UPLOAD_FOLDER: O caminho absoluto no servidor onde os arquivos de mídia serão salvos.

config.json: Para os endpoints do Fuseki e outros parâmetros. Verifique se as URLs correspondem à sua instância do Fuseki.

JSON

{
    "fuseki_url": "http://localhost:3030",
    "user_update_url": "http://localhost:3030/usuarios/update",
    "user_query_url": "http://localhost:3030/usuarios/query",
    "repo_update_url": "http://localhost:3030/repositoriosamigos/update",
    "repo_query_url": "http://localhost:3030/repositoriosamigos/query",
    "...": "..."
}
Executando a Aplicação
Modo de Desenvolvimento:

Com o seu ambiente virtual ativado e as configurações prontas, execute o seguinte comando:

Bash

python app.py
O servidor Flask será iniciado, geralmente em http://localhost:5000.

Modo de Produção:

Para produção, não é recomendado usar o servidor de desenvolvimento do Flask. Utilize um servidor WSGI como o Gunicorn:

Bash

# Exemplo de comando com Gunicorn
gunicorn --workers 4 --bind 0.0.0.0:5000 app:create_app()
Estrutura da API
A API é organizada em módulos (Blueprints), cada um com um prefixo de URL:

/acesso: Endpoints para autenticação e gerenciamento de usuários.

/repositorios: Gerenciamento de metadados de repositórios.

/classapi: Operações CRUD para classes da ontologia.

/fis: Operações CRUD para Objetos Físicos.

/dim: Operações CRUD para Objetos Dimensionais (Pessoa, Evento, etc.).

/relation: Gerenciamento de relações (triplas RDF).

/uploadapi: Upload e remoção de mídias.

/midias: Listagem de mídias associadas a objetos.

/graph: Endpoint para carregar os dados para a visualização principal.

Documentação da API (Swagger)
A API é autodocumentada usando Swagger UI. Após iniciar a aplicação, você pode acessar a documentação interativa no seu navegador:

http://localhost:5000/apidocs/

Lá você encontrará todos os endpoints, seus parâmetros, e poderá testá-los diretamente.