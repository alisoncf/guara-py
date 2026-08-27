"""
Módulo de Recomendação Semântica para o Sistema Guará
=======================================================

Protótipo experimental que usa o BERTimbau (NeuralMind) para gerar embeddings
das descrições textuais de objetos digitais do acervo, calcular similaridade
semântica entre eles, e sugerir conexões (relações) entre objetos de acervos
distintos — complementando o algoritmo de interoperabilidade estrutural já
existente no Guará (baseado em consultas SPARQL sobre a ontologia).

Requisitos:
    pip install sentence-transformers rdflib SPARQLWrapper scikit-learn pandas numpy

Uso típico (fim-a-fim):
    1. extrair_objetos_do_guara()   -> consulta o endpoint SPARQL do Guará
    2. gerar_embeddings()           -> BERTimbau via sentence-transformers
    3. calcular_similaridades()     -> matriz de similaridade de cosseno
    4. avaliar_contra_curadoria()   -> compara com relações :quem/:oque/:onde/:quando
                                        já existentes (gold standard informal)
    5. recomendar_novas_conexoes()  -> sugestões acima de um limiar, para revisão humana

Autor: rascunho de apoio técnico — revisar e adaptar antes de publicar/usar em produção.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


# ---------------------------------------------------------------------------
# 1. EXTRAÇÃO DE DADOS DO GUARÁ (via SPARQL)
# ---------------------------------------------------------------------------

# Namespaces reais confirmados via consulta ao Fuseki (guaraonto.owl):
#   objetos:  http://guara.ueg.br/ontologias/v1/objetos#   -> classes/propriedades da ontologia
#   classdef: http://guara.ueg.br/ontologias/v1/classdef#  -> hierarquia de classes de acervo
#   dc:       http://purl.org/dc/terms/                    -> title/description/abstract/subject
#
# IMPORTANTE (confirmado nos dados reais): os indivíduos usam dc:title e
# dc:description DIRETAMENTE (não as propriedades locais :titulo/:descricao,
# que existem na ontologia como subPropertyOf mas não aparecem populadas nos
# exemplos). Alguns objetos (ex. classe :Lugar) usam dc:abstract em vez de
# dc:description para o texto longo — por isso a query usa UNION/OPTIONAL
# para capturar title + (description OU abstract), o que for encontrado.
#
# :oque e :quando EXISTEM na ontologia (domain :ObjetoDigital, range :Evento
# e :Tempo) mas não apareciam na amostra inicial por ainda não estarem
# populados com dados. Mantidos na query de relações — vão aparecer assim
# que o acervo crescer.

SPARQL_QUERY_OBJETOS = """
PREFIX dc: <http://purl.org/dc/terms/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX obj: <http://guara.ueg.br/ontologias/v1/objetos#>

SELECT ?objeto ?tipo ?titulo ?texto_descritivo ?colecao
WHERE {
    ?objeto dc:title ?titulo .
    OPTIONAL { ?objeto rdf:type ?tipo }
    OPTIONAL { ?objeto obj:colecao ?colecao }
    OPTIONAL {
        { ?objeto dc:description ?texto_descritivo }
        UNION
        { ?objeto dc:abstract ?texto_descritivo }
    }
}
"""

# Consulta para extrair as relações JÁ existentes (curadas manualmente) — usadas
# como padrão-ouro informal para avaliar o quanto o modelo "redescobre" via
# similaridade semântica pura (sem supervisão).
SPARQL_QUERY_RELACOES_EXISTENTES = """
PREFIX obj: <http://guara.ueg.br/ontologias/v1/objetos#>

SELECT ?objeto ?propriedade ?alvo
WHERE {
    VALUES ?propriedade { obj:quem obj:oque obj:onde obj:quando }
    ?objeto ?propriedade ?alvo .
}
"""


def extrair_objetos_do_guara(endpoint_url: str) -> pd.DataFrame:
    """Consulta o endpoint SPARQL do Guará e retorna um DataFrame com os
    objetos digitais e suas descrições textuais (título + descrição
    concatenados, que é o texto que vai para o BERTimbau).
    """
    from SPARQLWrapper import SPARQLWrapper, JSON

    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(SPARQL_QUERY_OBJETOS)
    sparql.setReturnFormat(JSON)
    resultados = sparql.query().convert()

    linhas = []
    for r in resultados["results"]["bindings"]:
        linhas.append({
            "objeto_uri": r["objeto"]["value"],
            "tipo": r.get("tipo", {}).get("value", ""),
            "titulo": r.get("titulo", {}).get("value", ""),
            "descricao": r.get("texto_descritivo", {}).get("value", ""),
            "colecao": r.get("colecao", {}).get("value", ""),
        })

    df = pd.DataFrame(linhas)
    # Alguns objetos digitais têm múltiplas linhas (ex.: mais de um rdf:type,
    # como owl:NamedIndividual + a classe dimensional específica) — agrupa
    # por URI e mantém o tipo mais específico (o que não é owl:NamedIndividual).
    if not df.empty:
        df = (
            df.sort_values("tipo", key=lambda s: s.str.contains("NamedIndividual"))
            .drop_duplicates(subset="objeto_uri", keep="first")
            .reset_index(drop=True)
        )
    df["texto"] = (df["titulo"].fillna("") + ". " + df["descricao"].fillna("")).str.strip()
    return df


def extrair_relacoes_existentes(endpoint_url: str) -> pd.DataFrame:
    """Extrai as relações :quem/:oque/:onde/:quando já anotadas pelos
    curadores — servem de padrão-ouro informal para a avaliação de recall.
    """
    from SPARQLWrapper import SPARQLWrapper, JSON

    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(SPARQL_QUERY_RELACOES_EXISTENTES)
    sparql.setReturnFormat(JSON)
    resultados = sparql.query().convert()

    linhas = []
    for r in resultados["results"]["bindings"]:
        linhas.append({
            "objeto_uri": r["objeto"]["value"],
            "propriedade": r["propriedade"]["value"],
            "alvo_uri": r["alvo"]["value"],
        })
    return pd.DataFrame(linhas)


def carregar_dados_exemplo() -> pd.DataFrame:
    """Fallback SEM endpoint: mistura (a) os indivíduos de exemplo que já
    estão de fato carregados no guaraonto.owl (Einstein, Independência do
    Brasil, Palácio Rio Branco, Século XX — dados reais retornados pelo seu
    Fuseki) com (b) exemplos de festas populares descritos nos artigos
    (Folia de São João de Lagolândia etc.), só para validar o pipeline
    enquanto o acervo de festas_populares ainda está sendo populado.
    Substituir por extrair_objetos_do_guara() assim que houver dados suficientes.
    """
    exemplos = [
        # --- indivíduos reais já presentes no guaraonto.owl ---
        {
            "objeto_uri": "obj:Albert_Einstein",
            "tipo": "Pessoa",
            "titulo": "Albert Einstein",
            "descricao": "Físico teórico alemão, autor da teoria da relatividade.",
            "colecao": "",
        },
        {
            "objeto_uri": "obj:Independencia_Brasil",
            "tipo": "Evento",
            "titulo": "Independência do Brasil",
            "descricao": "Evento histórico que marcou a independência do Brasil de Portugal.",
            "colecao": "",
        },
        {
            "objeto_uri": "obj:Palacio_Rio_Branco",
            "tipo": "Lugar",
            "titulo": "Palácio Rio Branco",
            "descricao": "Palácio histórico em Salvador, Bahia, Brasil.",
            "colecao": "",
        },
        {
            "objeto_uri": "obj:Seculo_XX",
            "tipo": "Tempo",
            "titulo": "Século XX",
            "descricao": "Período histórico que abrange o século XX.",
            "colecao": "",
        },
        # --- exemplos de festas populares (dos artigos, para simular o domínio real) ---
        {
            "objeto_uri": "obj:entre_giros_esmolas",
            "tipo": "ObjetoFisico",
            "titulo": "Entre giros e esmolas, donzelas",
            "descricao": (
                "Documento arquivístico-documental, bibliotecário e "
                "imagético-sonoro que traz informações, fotografias e "
                "depoimentos da Festa de São João de Lagolândia, "
                "pertencente ao acervo de folias."
            ),
            "colecao": "Festas de Folia",
        },
        {
            "objeto_uri": "obj:folia_sao_joao_lagolandia",
            "tipo": "Evento",
            "titulo": "Folia de São João de Lagolândia",
            "descricao": (
                "Evento de manifestação do catolicismo popular realizado "
                "desde meados dos anos 1930 no povoado de Lagolândia, "
                "associado à figura histórica Benedita Gomes Cypriano, "
                "conhecida como Dona Dica."
            ),
            "colecao": "Festas de Folia",
        },
        {
            "objeto_uri": "obj:dona_dica",
            "tipo": "Pessoa",
            "titulo": "Benedita Gomes Cypriano (Dona Dica)",
            "descricao": (
                "Figura histórica e liderança religiosa e política da "
                "primeira metade do século XX em Lagolândia, "
                "reconhecida pela comunidade."
            ),
            "colecao": "",
        },
        {
            "objeto_uri": "obj:cavalhada_pirenopolis",
            "tipo": "Evento",
            "titulo": "Cavalhada de Pirenópolis",
            "descricao": (
                "Manifestação teatralizada que representa as Cruzadas "
                "travadas na Península Ibérica contra o avanço árabe, "
                "encenando lutas entre mouros e cristãos."
            ),
            "colecao": "Cavalhadas",
        },
        {
            "objeto_uri": "obj:congada_rosario",
            "tipo": "Evento",
            "titulo": "Congada de Nossa Senhora do Rosário",
            "descricao": (
                "Expressão afro-brasileira cultural, religiosa e "
                "devocional que combina desfiles, cantos e danças em "
                "honra a Nossa Senhora do Rosário."
            ),
            "colecao": "Congadas",
        },
    ]
    df = pd.DataFrame(exemplos)
    df["texto"] = (df["titulo"] + ". " + df["descricao"]).str.strip()
    return df


# ---------------------------------------------------------------------------
# 2. GERAÇÃO DE EMBEDDINGS COM BERTIMBAU
# ---------------------------------------------------------------------------

@dataclass
class ModeloEmbeddings:
    """Wrapper simples em torno do BERTimbau via sentence-transformers.

    NOTA: BERTimbau não foi treinado nativamente como sentence-encoder (ao
    contrário de modelos da família sentence-transformers/SBERT). Duas
    estratégias são possíveis:
      (a) mean pooling sobre a última camada oculta do BERTimbau puro
          (mais simples, mas menos calibrado para similaridade de frases);
      (b) usar uma versão do BERTimbau já adaptada para STS/similaridade
          textual (ex. fine-tunings da comunidade no Hugging Face Hub) —
          RECOMENDADO se disponível, pois a própria avaliação original do
          BERTimbau já usa STS como uma das tarefas de benchmark.
    Este wrapper implementa a opção (a) via transformers puro + mean pooling,
    que funciona com o checkpoint oficial neuralmind/bert-base-portuguese-cased.
    """
    modelo_nome: str = "neuralmind/bert-base-portuguese-cased"
    _tokenizer: object = field(default=None, repr=False)
    _modelo: object = field(default=None, repr=False)

    def carregar(self):
        from transformers import AutoTokenizer, AutoModel
        import torch  # noqa: F401  (garante que torch está instalado)

        self._tokenizer = AutoTokenizer.from_pretrained(self.modelo_nome)
        self._modelo = AutoModel.from_pretrained(self.modelo_nome)
        self._modelo.eval()
        return self

    def _mean_pooling(self, model_output, attention_mask):
        import torch

        token_embeddings = model_output[0]  # (batch, seq_len, hidden)
        mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        soma = torch.sum(token_embeddings * mask, dim=1)
        contagem = torch.clamp(mask.sum(dim=1), min=1e-9)
        return soma / contagem

    def embed(self, textos: list[str], batch_size: int = 16) -> np.ndarray:
        import torch

        if self._modelo is None:
            self.carregar()

        todos_embeddings = []
        with torch.no_grad():
            for i in range(0, len(textos), batch_size):
                lote = textos[i:i + batch_size]
                encoded = self._tokenizer(
                    lote, padding=True, truncation=True,
                    max_length=256, return_tensors="pt",
                )
                saida = self._modelo(**encoded)
                pooled = self._mean_pooling(saida, encoded["attention_mask"])
                todos_embeddings.append(pooled.cpu().numpy())

        return np.vstack(todos_embeddings)


def gerar_embeddings(df: pd.DataFrame, modelo: Optional[ModeloEmbeddings] = None) -> np.ndarray:
    """Gera embeddings BERTimbau para a coluna 'texto' do DataFrame."""
    modelo = modelo or ModeloEmbeddings()
    return modelo.embed(df["texto"].tolist())


# ---------------------------------------------------------------------------
# 3. SIMILARIDADE E RECOMENDAÇÃO
# ---------------------------------------------------------------------------

def calcular_similaridades(embeddings: np.ndarray) -> np.ndarray:
    """Matriz de similaridade de cosseno NxN entre todos os objetos."""
    return cosine_similarity(embeddings)


def recomendar_top_k(df: pd.DataFrame, matriz_sim: np.ndarray, k: int = 5,
                      limiar: float = 0.0) -> pd.DataFrame:
    """Para cada objeto, retorna os top-k objetos mais similares (excluindo
    ele mesmo), acima de um limiar mínimo de similaridade.

    Este é o "modo descoberta no acervo": varredura pareada entre TODOS os
    objetos, útil para achar duplicatas e conexões não percebidas no acervo
    inteiro (o que alimenta a avaliação de recall contra a curadoria manual).
    """
    n = len(df)
    linhas = []
    for i in range(n):
        similares = [(j, matriz_sim[i, j]) for j in range(n) if j != i and matriz_sim[i, j] >= limiar]
        similares.sort(key=lambda x: x[1], reverse=True)
        for j, score in similares[:k]:
            linhas.append({
                "objeto_origem": df.iloc[i]["objeto_uri"],
                "titulo_origem": df.iloc[i]["titulo"],
                "objeto_recomendado": df.iloc[j]["objeto_uri"],
                "titulo_recomendado": df.iloc[j]["titulo"],
                "similaridade": round(float(score), 4),
            })
    return pd.DataFrame(linhas)


# Classes dimensionais reconhecidas pela ontologia (obj:Pessoa, obj:Evento,
# obj:Lugar, obj:Tempo) — usadas para filtrar o "modo assistente de curadoria"
# apenas às entidades que podem ser alvo de :quem/:oque/:onde/:quando.
DIMENSAO_POR_TIPO = {
    "Pessoa": "quem",
    "Evento": "oque",
    "Lugar": "onde",
    "Tempo": "quando",
}


def sugerir_ligacoes_para_novo_objeto(
    texto_novo_objeto: str,
    df_acervo: pd.DataFrame,
    embeddings_acervo: np.ndarray,
    modelo: Optional["ModeloEmbeddings"] = None,
    top_k_por_dimensao: int = 3,
    limiar: float = 0.5,
) -> pd.DataFrame:
    """MODO ASSISTENTE DE CURADORIA — o fluxo real de uso no Guará.

    Um curador cadastra um objeto novo (ex.: um documento recém-digitalizado,
    com título + descrição). Esta função gera o embedding desse texto e o
    compara SÓ com as entidades dimensionais já existentes no acervo
    (instâncias de Pessoa, Evento, Lugar, Tempo) — não com todo e qualquer
    objeto — e devolve, por dimensão, as melhores sugestões de ligação
    (candidatas a virarem triplos :quem/:oque/:onde/:quando após confirmação
    humana do curador).

    Parâmetros:
        texto_novo_objeto:   título + descrição do objeto recém-cadastrado
                              (mesmo formato usado para compor a coluna
                              'texto' no restante do pipeline: "Título. Descrição").
        df_acervo:            DataFrame já carregado (extrair_objetos_do_guara
                               ou carregar_dados_exemplo), com a coluna 'tipo'
                               preenchida — necessário para filtrar por dimensão.
        embeddings_acervo:    embeddings já calculados para df_acervo (reaproveita
                               o que gerar_embeddings() produziu, evita recomputar
                               o acervo inteiro a cada novo objeto).
        modelo:               instância de ModeloEmbeddings já carregada (reaproveita
                               o modelo em memória); se None, carrega uma nova.
        top_k_por_dimensao:   quantas sugestões trazer para cada uma das 4 dimensões.
        limiar:                similaridade mínima para uma sugestão aparecer.

    Retorna um DataFrame com colunas:
        dimensao, propriedade_sugerida, objeto_uri, titulo, similaridade
    Pronto para virar a tabela "sugestões do assistente de curadoria" no artigo.
    """
    modelo = modelo or ModeloEmbeddings()
    embedding_novo = modelo.embed([texto_novo_objeto])  # shape (1, hidden)

    linhas = []
    for dimensao, propriedade in DIMENSAO_POR_TIPO.items():
        # Filtra só as entidades dimensionais do tipo certo (ex.: só Pessoa
        # para a propriedade :quem). O campo 'tipo' vem do rdf:type — pode
        # conter a URI completa ou só o nome da classe, então checamos com
        # 'in' em vez de igualdade exata.
        mascara = df_acervo["tipo"].fillna("").str.contains(dimensao, case=False)
        indices_candidatos = np.where(mascara.to_numpy())[0]
        if len(indices_candidatos) == 0:
            continue

        sims = cosine_similarity(embedding_novo, embeddings_acervo[indices_candidatos])[0]
        pares = sorted(zip(indices_candidatos, sims), key=lambda x: x[1], reverse=True)

        for idx, score in pares[:top_k_por_dimensao]:
            if score < limiar:
                continue
            linhas.append({
                "dimensao": dimensao,
                "propriedade_sugerida": f":{propriedade}",
                "objeto_uri": df_acervo.iloc[idx]["objeto_uri"],
                "titulo": df_acervo.iloc[idx]["titulo"],
                "similaridade": round(float(score), 4),
            })

    resultado = pd.DataFrame(linhas)
    if not resultado.empty:
        resultado = resultado.sort_values(
            ["dimensao", "similaridade"], ascending=[True, False]
        ).reset_index(drop=True)
    return resultado


# ---------------------------------------------------------------------------
# 4. AVALIAÇÃO CONTRA O PADRÃO-OURO (relações já curadas manualmente)
# ---------------------------------------------------------------------------

def avaliar_contra_curadoria(recomendacoes: pd.DataFrame,
                              relacoes_existentes: pd.DataFrame,
                              k: int = 5) -> dict:
    """Calcula recall@k: das relações já anotadas manualmente pelos
    curadores, quantas o modelo teria sugerido dentro do top-k por
    similaridade pura (sem qualquer supervisão)?

    Isso NÃO mede se o modelo "acertou" no sentido de aprovação humana —
    mede o quanto a similaridade textual sozinha já recupera decisões
    curatoriais reais. É uma métrica de recall, não de precisão; a precisão
    (quantas das sugestões extras fazem sentido) precisa da rodada de
    avaliação humana qualitativa.
    """
    pares_curados = set(
        zip(relacoes_existentes["objeto_uri"], relacoes_existentes["alvo_uri"])
    )
    pares_recomendados = set(
        zip(recomendacoes["objeto_origem"], recomendacoes["objeto_recomendado"])
    )

    acertos = pares_curados & pares_recomendados
    recall = len(acertos) / len(pares_curados) if pares_curados else float("nan")

    return {
        "total_relacoes_curadas": len(pares_curados),
        "total_recomendacoes_geradas": len(pares_recomendados),
        "acertos_recall_at_k": len(acertos),
        "recall_at_k": round(recall, 4),
        "k": k,
    }


# ---------------------------------------------------------------------------
# 5. EXECUÇÃO / DEMONSTRAÇÃO
# ---------------------------------------------------------------------------

def main(endpoint_url: Optional[str] = None, texto_objeto_novo_demo: Optional[str] = None):
    if endpoint_url:
        print(f"Consultando endpoint real: {endpoint_url}")
        df = extrair_objetos_do_guara(endpoint_url)
        relacoes = extrair_relacoes_existentes(endpoint_url)
    else:
        print("Sem endpoint configurado — usando dados de exemplo para validar o pipeline.")
        df = carregar_dados_exemplo()
        relacoes = pd.DataFrame(columns=["objeto_uri", "propriedade", "alvo_uri"])

    print(f"\n{len(df)} objetos carregados.")
    print("Gerando embeddings com BERTimbau (pode demorar na primeira execução "
          "— faz download do checkpoint do Hugging Face)...")

    modelo = ModeloEmbeddings().carregar()
    embeddings = gerar_embeddings(df, modelo=modelo)
    matriz_sim = calcular_similaridades(embeddings)

    # --- Modo 1: descoberta no acervo (pareado, todos contra todos) ---
    recomendacoes = recomendar_top_k(df, matriz_sim, k=3, limiar=0.5)
    print("\n=== MODO 1 — Descoberta no acervo (top-3 por objeto, similaridade >= 0.5) ===")
    print(recomendacoes.to_string(index=False))

    if not relacoes.empty:
        avaliacao = avaliar_contra_curadoria(recomendacoes, relacoes, k=3)
        print("\n=== Avaliação contra relações curadas manualmente ===")
        print(json.dumps(avaliacao, ensure_ascii=False, indent=2))

    # --- Modo 2: assistente de curadoria (objeto novo -> sugestões por dimensão) ---
    # Exemplo de demonstração: um documento novo, ainda sem nenhuma relação
    # :quem/:oque/:onde/:quando cadastrada, que o curador acabou de subir.
    texto_demo = texto_objeto_novo_demo or (
        "Relato da Folia de Reis em Lagolândia. Depoimento de uma moradora "
        "sobre a passagem dos foliões pela casa de Dona Dica em janeiro, "
        "com fotos do giro pelas ruas do povoado."
    )
    print(f"\n=== MODO 2 — Assistente de curadoria ===")
    print(f"Objeto novo (texto de entrada): \"{texto_demo}\"\n")
    sugestoes = sugerir_ligacoes_para_novo_objeto(
        texto_demo, df, embeddings, modelo=modelo, top_k_por_dimensao=3, limiar=0.4,
    )
    if sugestoes.empty:
        print("Nenhuma sugestão acima do limiar — experimente baixar o parâmetro 'limiar'.")
    else:
        print(sugestoes.to_string(index=False))

    # Salva os resultados para uso no artigo (tabelas, gráficos etc.)
    recomendacoes.to_csv("/home/claude/guara_bertimbau/recomendacoes.csv", index=False)
    sugestoes.to_csv("/home/claude/guara_bertimbau/sugestoes_assistente_curadoria.csv", index=False)
    print("\nRecomendações salvas em recomendacoes.csv")
    print("Sugestões do assistente de curadoria salvas em sugestoes_assistente_curadoria.csv")


if __name__ == "__main__":
    # Trocar por: main(endpoint_url="https://guara.ueg.br/fuseki/festas_populares/sparql")
    # Também dá pra passar um texto real de objeto novo para testar o modo 2:
    # main(endpoint_url=None, texto_objeto_novo_demo="Título. Descrição do objeto novo.")
    main(endpoint_url=None)