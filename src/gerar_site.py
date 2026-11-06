"""Gera os dados compactos do site estático (GitHub Pages).

O Pages só serve arquivos estáticos, então o Python roda aqui, antes da
publicação: lê os Parquet, codifica cada coluna em binário e grava em
site/assets. O navegador apenas filtra e desenha.

Uso:
    python src/gerar_site.py
"""
import gzip
import json

import numpy as np
import pandas as pd

from config import ACIDENTES_PARQUET, PESSOAS_PARQUET, RAIZ

SAIDA = RAIZ / "site" / "assets"
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
NAO_INFORMADO = "Não informado"


def unificar_grafia(serie: pd.Series) -> pd.Series:
    """Junta categorias que só diferem em maiúsculas, usando a grafia mais comum."""
    contagem = serie.value_counts()
    grafia = {}
    for valor in contagem.index:
        grafia.setdefault(valor.casefold().strip(), valor)
    return serie.map(lambda v: grafia[v.casefold().strip()], na_action="ignore")


def codificar(serie: pd.Series, ordem=None):
    """Troca texto por índice. Devolve (códigos uint8, lista de categorias)."""
    serie = serie.astype("object").where(serie.notna(), NAO_INFORMADO)
    categorias = ordem if ordem is not None else sorted(serie.unique(), key=str)
    mapa = {valor: i for i, valor in enumerate(categorias)}
    codigos = serie.map(mapa)
    if codigos.isna().any() or len(categorias) > 255:
        raise ValueError(f"categoria inesperada em {serie.name}")
    return codigos.to_numpy(dtype=np.uint8), [str(c) for c in categorias]


class Pacote:
    """Concatena colunas num único binário, com offsets alinhados a 4 bytes."""

    def __init__(self):
        self.partes, self.tamanho, self.colunas = [], 0, {}

    def adicionar(self, nome, valores):
        valores = np.ascontiguousarray(valores)
        self.colunas[nome] = {
            "tipo": valores.dtype.name, "offset": self.tamanho, "n": int(valores.size),
        }
        bruto = valores.tobytes()
        enchimento = -len(bruto) % 4
        self.partes.append(bruto + b"\0" * enchimento)
        self.tamanho += len(bruto) + enchimento


def tabela_pessoas(pacote, prefixo, grupos):
    """Grava uma tabela agregada (uma coluna por dimensão + contagem n)."""
    colunas = list(grupos.columns)
    resumo = grupos.groupby(colunas, observed=True).size().reset_index(name="n")
    for col in colunas:
        pacote.adicionar(f"{prefixo}_{col}", resumo[col].to_numpy(dtype=np.uint8))
    pacote.adicionar(f"{prefixo}_n", resumo["n"].to_numpy(dtype=np.uint32))


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    a = pd.read_parquet(ACIDENTES_PARQUET).sort_values(["ano", "uf", "br", "data_hora"], ignore_index=True)
    p = pd.read_parquet(
        PESSOAS_PARQUET,
        columns=["id", "tipo_veiculo", "tipo_envolvido", "estado_fisico", "faixa_etaria", "sexo"],
    )

    a["causa_acidente"] = unificar_grafia(a["causa_acidente"])
    a["tipo_acidente"] = unificar_grafia(a["tipo_acidente"])

    pacote = Pacote()
    categorias = {}
    anos = sorted(int(x) for x in a["ano"].unique())
    ano = (a["ano"].astype(int) - anos[0]).to_numpy(dtype=np.uint8)
    brs = sorted(int(x) for x in a["br"].unique())
    br = a["br"].astype(int).map({b: i for i, b in enumerate(brs)}).to_numpy(dtype=np.uint8)

    pacote.adicionar("ano", ano)
    pacote.adicionar("mes", (a["mes"].astype(int) - 1).to_numpy(dtype=np.uint8))
    pacote.adicionar("dia", a["dia_semana"].cat.codes.to_numpy(dtype=np.uint8))
    pacote.adicionar("hora", a["hora"].astype(int).to_numpy(dtype=np.uint8))
    pacote.adicionar("br", br)
    for coluna, nome in [
        ("uf", "uf"), ("fase_dia", "fase"), ("causa_acidente", "causa"), ("tipo_acidente", "tipo"),
        ("condicao_meteorologica", "clima"), ("tipo_pista", "pista"), ("uso_solo", "solo"),
        ("classificacao_acidente", "classe"),
    ]:
        codigos, categorias[nome] = codificar(a[coluna].rename(nome))
        pacote.adicionar(nome, codigos)
        if nome == "uf":
            uf = codigos
    for coluna, nome in [("mortos", "mortos"), ("feridos_graves", "graves"), ("feridos_leves", "leves")]:
        pacote.adicionar(nome, a[coluna].fillna(0).astype(int).to_numpy(dtype=np.uint8))

    # Trecho de 10 km: código por (trecho, UF) e município mais frequente como referência
    chave = a["trecho"].fillna("") + "|" + a["uf"]
    codigos_trecho, nomes_trecho = pd.factorize(chave, sort=True)
    pacote.adicionar("trecho", codigos_trecho.astype(np.uint16))
    municipio = a.groupby(chave)["municipio"].agg(lambda s: s.mode().iat[0])
    trechos = [
        {"nome": k.split("|")[0], "uf": k.split("|")[1], "municipio": municipio[k].title()}
        for k in nomes_trecho
    ]

    # Pontos do mapa: só acidentes fatais com coordenada válida
    pontos = a.index[a["fatal"] & a["latitude"].notna()].to_numpy()
    pacote.adicionar("mapa_linha", pontos.astype(np.uint32))
    pacote.adicionar("mapa_lat", a.loc[pontos, "latitude"].to_numpy(dtype=np.float32))
    pacote.adicionar("mapa_lon", a.loc[pontos, "longitude"].to_numpy(dtype=np.float32))

    # Pessoas: agregadas por dimensão, herdando os filtros do acidente
    dims = pd.DataFrame({"id": a["id"], "ano": ano, "uf": uf, "br": br,
                         "fatal": a["fatal"].astype(np.uint8)})
    p = p.merge(dims, on="id", how="inner")
    base = ["ano", "uf", "br", "fatal"]

    obitos = p[p["estado_fisico"] == "Óbito"].copy()
    obitos["veiculo"], categorias["veiculo"] = codificar(obitos["tipo_veiculo"].rename("veiculo"))
    tabela_pessoas(pacote, "veic", obitos[base + ["veiculo"]])

    p["papel"], categorias["papel"] = codificar(p["tipo_envolvido"].rename("papel"))
    tabela_pessoas(pacote, "papel", p[base + ["papel"]])

    faixas = list(p["faixa_etaria"].cat.categories)
    vitimas = p[p["estado_fisico"].isin(["Óbito", "Lesões Graves"])
                & p["sexo"].isin(["Masculino", "Feminino"]) & p["faixa_etaria"].notna()].copy()
    vitimas["faixa"], categorias["faixa"] = codificar(vitimas["faixa_etaria"].astype(str).rename("faixa"), faixas)
    vitimas["sexo_c"], categorias["sexo"] = codificar(vitimas["sexo"].rename("sexo"), ["Masculino", "Feminino"])
    tabela_pessoas(pacote, "vit", vitimas[base + ["faixa", "sexo_c"]])

    meta = {
        "linhas": len(a), "anos": anos, "brs": brs, "dias": DIAS,
        "categorias": categorias, "trechos": trechos, "colunas": pacote.colunas,
    }
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with gzip.open(SAIDA / "dados.bin.gz", "wb", compresslevel=9) as f:
        for parte in pacote.partes:
            f.write(parte)

    tamanho = (SAIDA / "dados.bin.gz").stat().st_size / 1e6
    print(f"{len(a):,} acidentes, {len(pontos):,} pontos no mapa, {len(trechos):,} trechos")
    print(f"dados.bin.gz: {tamanho:.1f} MB")


if __name__ == "__main__":
    main()
