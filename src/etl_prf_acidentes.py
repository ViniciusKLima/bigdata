"""ETL dos acidentes da PRF (2019 em diante).

Lê os CSVs brutos (latin1, separador ';', vírgula decimal), padroniza tipos,
cria colunas derivadas e grava em Parquet na pasta dados/processado.

Uso:
    python src/etl_prf_acidentes.py
"""
import time

import numpy as np
import pandas as pd

from config import (
    ACIDENTES_PARQUET,
    PESSOAS_PARQUET,
    PRF_OCORRENCIAS,
    PRF_PESSOAS,
    PROCESSADO,
)

COLUNAS_DECIMAIS = ["km", "latitude", "longitude"]
COLUNAS_INTEIRAS = [
    "br", "pessoas", "mortos", "feridos_leves", "feridos_graves", "ilesos",
    "ignorados", "feridos", "veiculos", "idade", "ano_fabricacao_veiculo",
    "id", "pesid", "id_veiculo",
]
DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]
# Retângulo que envolve o território brasileiro
LAT_MIN, LAT_MAX = -34.0, 5.5
LON_MIN, LON_MAX = -74.0, -34.0


def ler_csvs(pasta) -> pd.DataFrame:
    partes = []
    for arquivo in sorted(pasta.glob("*.csv")):
        df = pd.read_csv(
            arquivo,
            sep=";",
            encoding="latin1",
            dtype=str,
            na_values=["NA", "", "(null)", "NULL"],
            keep_default_na=False,
        )
        print(f"  {arquivo.name}: {len(df):,} linhas")
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def padronizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"condicao_metereologica": "condicao_meteorologica"})

    # Texto: remove espaços sobrando
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    for col in COLUNAS_DECIMAIS:
        if col in df:
            df[col] = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")

    for col in COLUNAS_INTEIRAS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Data e hora
    df["data"] = pd.to_datetime(df.pop("data_inversa"), errors="coerce")
    df["data_hora"] = pd.to_datetime(
        df["data"].dt.strftime("%Y-%m-%d") + " " + df["horario"].fillna("00:00:00"),
        errors="coerce",
    )
    df["ano"] = df["data"].dt.year.astype("Int16")
    df["mes"] = df["data"].dt.month.astype("Int8")
    df["hora"] = df["data_hora"].dt.hour.astype("Int8")
    df["dia_semana"] = pd.Categorical(df["dia_semana"].str.lower(), categories=DIAS_SEMANA, ordered=True)

    # Coordenadas fora do Brasil viram nulas
    fora = ~(
        df["latitude"].between(LAT_MIN, LAT_MAX) & df["longitude"].between(LON_MIN, LON_MAX)
    )
    df.loc[fora, ["latitude", "longitude"]] = np.nan

    # Trecho de 10 km da rodovia, ex.: "BR-101 km 120-130"
    trecho_ini = (df["km"] // 10 * 10).astype("Int64")
    df["trecho"] = (
        "BR-" + df["br"].astype(str).str.zfill(3) + " km "
        + trecho_ini.astype(str) + "-" + (trecho_ini + 10).astype(str)
    )
    df.loc[df["br"].isna() | df["km"].isna(), "trecho"] = None
    return df


def tratar_acidentes(df: pd.DataFrame) -> pd.DataFrame:
    df = padronizar(df)
    df["fatal"] = df["mortos"].fillna(0) > 0
    df["com_vitimas"] = (df["mortos"].fillna(0) + df["feridos"].fillna(0)) > 0
    return df.drop_duplicates(subset="id")


def tratar_pessoas(df: pd.DataFrame) -> pd.DataFrame:
    df = padronizar(df)
    df.loc[~df["idade"].between(0, 110), "idade"] = pd.NA
    df.loc[~df["ano_fabricacao_veiculo"].between(1950, 2026), "ano_fabricacao_veiculo"] = pd.NA
    df["faixa_etaria"] = pd.cut(
        df["idade"].astype("float"),
        bins=[0, 17, 24, 34, 44, 54, 64, 120],
        labels=["0-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
        include_lowest=True,
    )
    return df.drop_duplicates(subset=["id", "pesid"])


def main():
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    inicio = time.time()

    print("Acidentes (1 linha por ocorrência):")
    acidentes = tratar_acidentes(ler_csvs(PRF_OCORRENCIAS))
    acidentes.to_parquet(ACIDENTES_PARQUET, index=False)
    print(f"  -> {ACIDENTES_PARQUET.name}: {len(acidentes):,} linhas\n")

    print("Pessoas (1 linha por envolvido):")
    pessoas = tratar_pessoas(ler_csvs(PRF_PESSOAS))
    pessoas.to_parquet(PESSOAS_PARQUET, index=False)
    print(f"  -> {PESSOAS_PARQUET.name}: {len(pessoas):,} linhas\n")

    print(f"Concluído em {time.time() - inicio:.0f}s")


if __name__ == "__main__":
    main()
