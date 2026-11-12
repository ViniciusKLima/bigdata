"""Acrescenta o conjunto parcial de 2026 ao pacote estático já publicado.

Uso:
    python src/atualizar_site_2026.py
"""
import gzip
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baixar_dados import acidentes_2026
from config import PRF_OCORRENCIAS, PRF_PESSOAS
from etl_prf_acidentes import tratar_acidentes, tratar_pessoas
from gerar_site import Pacote, gerar_pacote

ASSETS = Path(__file__).resolve().parent.parent / "site" / "assets"
COLUNAS_PESSOAS = ["id", "tipo_veiculo", "tipo_envolvido", "estado_fisico", "faixa_etaria", "sexo"]


def ler_csv(arquivo):
    with zipfile.ZipFile(arquivo.with_suffix(".zip")) as pacote:
        nome = next((n for n in pacote.namelist() if n.lower().endswith(".csv")), None)
        if nome is None:
            raise ValueError(f"Nenhum CSV encontrado em {arquivo.with_suffix('.zip')}")
        with pacote.open(nome) as entrada:
            return pd.read_csv(
                entrada, sep=";", encoding="latin1", dtype=str,
                na_values=["NA", "", "(null)", "NULL"], keep_default_na=False,
            )


def ler_base(arquivo):
    if not arquivo.is_file():
        raise FileNotFoundError(f"Arquivo da PRF não encontrado: {arquivo}. Baixe novamente os dados de 2026.")
    return ler_csv(arquivo)


def mapa_indices(categorias_antigas, categorias_novas):
    unidas = list(categorias_antigas)
    for valor in categorias_novas:
        if valor not in unidas:
            unidas.append(valor)
    if len(unidas) > 256:
        raise ValueError("A lista de categorias ultrapassa o limite do formato compacto do site.")
    indices = {valor: i for i, valor in enumerate(unidas)}
    remapeamento = np.asarray([indices[valor] for valor in categorias_novas], dtype=np.uint8)
    return unidas, remapeamento


def carregar_arrays(caminho, meta):
    dados = gzip.open(caminho, "rb").read()
    return {
        nome: np.frombuffer(
            dados, dtype=np.dtype(coluna["tipo"]), count=coluna["n"], offset=coluna["offset"]
        ).copy()
        for nome, coluna in meta["colunas"].items()
    }


def remapear_ano(valores, anos_origem, anos_unidos):
    indices = {ano: i for i, ano in enumerate(anos_unidos)}
    return np.asarray([indices[anos_origem[int(valor)]] for valor in valores], dtype=np.uint8)


def remover_ano(meta, arrays, ano_remover):
    """Retira a versão anterior do ano para permitir atualizações sem duplicar registros."""
    if ano_remover not in meta["anos"]:
        return meta, arrays

    indice_ano = meta["anos"].index(ano_remover)
    manter_linhas = arrays["ano"] != indice_ano
    indice_linha = np.full(meta["linhas"], -1, dtype=np.int64)
    indice_linha[manter_linhas] = np.arange(np.count_nonzero(manter_linhas))

    manter_mapa = manter_linhas[arrays["mapa_linha"]]
    novas_colunas = {}
    for nome, valores in arrays.items():
        if nome == "mapa_linha":
            novas_colunas[nome] = indice_linha[valores[manter_mapa]].astype(valores.dtype)
        elif nome in ("mapa_lat", "mapa_lon"):
            novas_colunas[nome] = valores[manter_mapa]
        elif nome.startswith(("veic_", "papel_", "vit_")):
            prefixo = nome.split("_", 1)[0]
            manter_tabela = arrays[f"{prefixo}_ano"] != indice_ano
            novas_colunas[nome] = valores[manter_tabela]
        else:
            novas_colunas[nome] = valores[manter_linhas] if valores.size == meta["linhas"] else valores

    meta = {**meta, "anos": [ano for ano in meta["anos"] if ano != ano_remover],
            "linhas": int(np.count_nonzero(manter_linhas))}
    return meta, novas_colunas


def combinar_meta_e_dados(meta_antiga, arrays_antigos, meta_nova, arrays_novos, data_fim):
    anos = sorted(set(meta_antiga["anos"]) | set(meta_nova["anos"]))
    anos = [int(ano) for ano in anos]
    brs = sorted(set(meta_antiga["brs"]) | set(meta_nova["brs"]))
    brs = [int(br) for br in brs]
    indice_br = {br: i for i, br in enumerate(brs)}
    remap_br_antigo = np.asarray([indice_br[int(br)] for br in meta_antiga["brs"]], dtype=np.uint8)
    remap_br_novo = np.asarray([indice_br[int(br)] for br in meta_nova["brs"]], dtype=np.uint8)

    categorias = {}
    remaps = {}
    for nome, antigas in meta_antiga["categorias"].items():
        unidas, remap_novo = mapa_indices(antigas, meta_nova["categorias"].get(nome, antigas))
        categorias[nome] = unidas
        remaps[nome] = remap_novo

    trechos = list(meta_antiga["trechos"])
    indice_trecho = {(t["nome"], t["uf"]): i for i, t in enumerate(trechos)}
    remap_trecho_novo = []
    for trecho in meta_nova["trechos"]:
        chave = (trecho["nome"], trecho["uf"])
        if chave not in indice_trecho:
            indice_trecho[chave] = len(trechos)
            trechos.append(trecho)
        remap_trecho_novo.append(indice_trecho[chave])
    if len(trechos) > 65536:
        raise ValueError("O total de trechos ultrapassa o limite do formato compacto do site.")
    remap_trecho_novo = np.asarray(remap_trecho_novo, dtype=np.uint16)

    def ajustar(nome, valores, eh_novo):
        if nome == "ano" or nome.endswith("_ano"):
            return remapear_ano(valores, meta_nova["anos"] if eh_novo else meta_antiga["anos"], anos)
        if nome == "br" or nome.endswith("_br"):
            return remap_br_novo[valores] if eh_novo else remap_br_antigo[valores]
        if nome == "trecho":
            return remap_trecho_novo[valores] if eh_novo else valores
        if nome == "mapa_linha" and eh_novo:
            return valores + meta_antiga["linhas"]

        campo = nome if nome in categorias else None
        if campo is None:
            correspondencia = re.fullmatch(r"(veic|papel|vit)_(veiculo|papel|faixa|sexo_c)", nome)
            if correspondencia:
                campo = {"sexo_c": "sexo"}.get(correspondencia.group(2), correspondencia.group(2))
        if eh_novo and campo:
            return remaps[campo][valores]
        return valores

    pacote = Pacote()
    for nome in meta_antiga["colunas"]:
        if nome not in arrays_novos:
            raise ValueError(f"A coluna {nome} não foi gerada para 2026.")
        antigo = ajustar(nome, arrays_antigos[nome], False)
        novo = ajustar(nome, arrays_novos[nome], True)
        pacote.adicionar(nome, np.concatenate((antigo, novo)))

    meta = {
        **meta_antiga,
        "linhas": meta_antiga["linhas"] + meta_nova["linhas"],
        "anos": anos,
        "brs": brs,
        "trechos": trechos,
        "categorias": categorias,
        "colunas": pacote.colunas,
        "data_inicio": meta_antiga.get("data_inicio", "2019-01-01"),
        "data_fim": data_fim,
    }
    return meta, pacote


def main():
    print("Baixando os dados oficiais de acidentes da PRF para 2026...")
    acidentes_2026()
    acidentes = tratar_acidentes(ler_base(PRF_OCORRENCIAS / "datatran2026.csv"))
    pessoas = tratar_pessoas(ler_base(PRF_PESSOAS / "acidentes2026.csv"))[COLUNAS_PESSOAS].copy()
    acidentes = acidentes.sort_values(["ano", "uf", "br", "data_hora"], ignore_index=True)

    meta_nova, pacote_novo = gerar_pacote(acidentes, pessoas)
    binario_novo = b"".join(pacote_novo.partes)
    arrays_novos = {
        nome: np.frombuffer(
            binario_novo, dtype=np.dtype(coluna["tipo"]), count=coluna["n"], offset=coluna["offset"]
        ).copy()
        for nome, coluna in meta_nova["colunas"].items()
    }

    arquivo_meta = ASSETS / "meta.json"
    arquivo_dados = ASSETS / "dados.bin.gz"
    meta_antiga = json.loads(arquivo_meta.read_text(encoding="utf-8"))
    arrays_antigos = carregar_arrays(arquivo_dados, meta_antiga)
    meta_antiga, arrays_antigos = remover_ano(meta_antiga, arrays_antigos, 2026)
    data_fim = acidentes["data"].max().date().isoformat()
    meta, pacote = combinar_meta_e_dados(
        meta_antiga, arrays_antigos, meta_nova, arrays_novos, data_fim
    )

    meta_temporaria = arquivo_meta.with_suffix(".json.tmp")
    dados_temporarios = arquivo_dados.with_suffix(".gz.tmp")
    meta_temporaria.write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    with gzip.open(dados_temporarios, "wb", compresslevel=9) as saida:
        for parte in pacote.partes:
            saida.write(parte)
    dados_temporarios.replace(arquivo_dados)
    meta_temporaria.replace(arquivo_meta)

    print(
        f"Site atualizado: {meta['linhas']:,} acidentes; "
        f"2026 contém {meta_nova['linhas']:,} registros até {data_fim} (dados parciais)."
    )
    print(f"Pacote: {arquivo_dados.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
