"""
Escape seguro para literais SPARQL/Turtle
===========================================

O backend do Guará monta queries SPARQL por concatenação de string (INSERT
DATA, DELETE/INSERT) em vez de usar um cliente com parâmetros vinculados.
Isso é uma injeção de SPARQL em potencial: qualquer aspa, barra invertida ou
quebra de linha dentro de um título/descrição vindo do usuário quebra a
sintaxe da query e faz o restante do texto ser interpretado como SPARQL, não
como dado — o que pode truncar ou corromper silenciosamente o conteúdo
gravado (foi o que aconteceu na dissertação sobre a Folia de São João, cuja
descrição gravada termina com um fragmento de sintaxe SPARQL vazado).

Este módulo fornece funções para escapar valores ANTES de inseri-los na
string da query. Aplique em toda rota que monta SPARQL por f-string.

Regras de escape de literais em Turtle/SPARQL (spec oficial):
  https://www.w3.org/TR/turtle/#grammar-production-STRING_LITERAL_QUOTE
Caracteres que precisam ser escapados dentro de uma string entre aspas
duplas: barra invertida, aspas duplas, quebra de linha, retorno de carro,
tab. A ORDEM importa — a barra invertida tem que ser escapada PRIMEIRO,
senão você escapa duas vezes o que acabou de escapar.
"""

import re

# Caracteres de controle não permitidos, mesmo escapados, dentro de uma
# string literal SPARQL de uma linha só (produção STRING_LITERAL_QUOTE) —
# removidos por segurança/simplicidade em vez de escapados, já que raramente
# são conteúdo legítimo de título/descrição.
_CONTROLE_PROIBIDO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def escapar_literal_sparql(valor: str) -> str:
    """Escapa um valor para uso seguro DENTRO de aspas duplas numa query
    SPARQL/Turtle montada por f-string, ex.:

        valor_seguro = escapar_literal_sparql(titulo_do_usuario)
        query = f'INSERT DATA {{ :{id} dc:title "{valor_seguro}" }}'

    NÃO inclui as aspas — só o conteúdo. Trata None como string vazia.
    """
    if valor is None:
        return ""
    if not isinstance(valor, str):
        valor = str(valor)

    # Ordem importa: barra invertida primeiro, senão escapamos duas vezes
    # as barras que acabamos de inserir nos passos seguintes.
    valor = valor.replace("\\", "\\\\")
    valor = valor.replace('"', '\\"')
    valor = valor.replace("\n", "\\n")
    valor = valor.replace("\r", "\\r")
    valor = valor.replace("\t", "\\t")
    valor = _CONTROLE_PROIBIDO.sub("", valor)
    return valor


# URIs completas (dentro de < >) têm regras próprias: não podem conter
# espaços, '<', '>', aspas, '{', '}', '|', '^', '`', ou caracteres de
# controle. Isso importa para a rota de sugestões que vamos criar, onde a
# URI do recurso recomendado vem de outro dado do próprio acervo — nunca
# assuma que é segura só porque "já está no banco".
_CARACTERES_INVALIDOS_URI = re.compile(r'[\s<>"{}|^`\x00-\x1f]')


def validar_uri_sparql(uri: str) -> str:
    """Valida que uma URI é segura para uso dentro de < > numa query
    SPARQL. Levanta ValueError se houver caractere inválido, em vez de
    tentar 'consertar' a URI silenciosamente — uma URI malformada deveria
    ser rejeitada com erro claro (400), não gravada de qualquer jeito.
    """
    if not uri or not isinstance(uri, str):
        raise ValueError("URI vazia ou inválida.")
    if _CARACTERES_INVALIDOS_URI.search(uri):
        raise ValueError(
            f"URI contém caractere não permitido em SPARQL: {uri!r}"
        )
    return uri


def escapar_id_sparql(object_id: str) -> str:
    """Para o :{object_id} usado como sufixo de URI local (ex. :abc-123).
    IDs costumam ser UUIDs gerados pelo próprio sistema, mas nunca confie
    cegamente em algo que chega via request.get_json() — valida como URI
    (sem os delimitadores < >, mas mesma regra de caracteres proibidos).
    """
    if not object_id or not isinstance(object_id, str):
        raise ValueError("id vazio ou inválido.")
    if _CARACTERES_INVALIDOS_URI.search(object_id):
        raise ValueError(
            f"id contém caractere não permitido em SPARQL: {object_id!r}"
        )
    return object_id
