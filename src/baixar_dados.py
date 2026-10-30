"""Baixa todas as fontes de dados brutos do projeto para a pasta dados/.

Fontes: PRF (acidentes e infrações), IBGE (municípios e população),
SENATRAN (frota) e INMET (clima). Arquivos já baixados são pulados.

Uso:
    python src/baixar_dados.py            # tudo
    python src/baixar_dados.py acidentes  # só um grupo (acidentes, infracoes, ibge, frota, inmet)
"""
import gzip
import shutil
import sys
import urllib.request
import zipfile

from config import DADOS

ANOS = range(2019, 2026)
DRIVE = "https://drive.usercontent.google.com/download?id={}&export=download&confirm=t"
GOV = "https://www.gov.br/transportes/pt-br/assuntos/transito"

# IDs dos arquivos no Google Drive da PRF (página "Dados Abertos da PRF")
PRF_OCORRENCIA = {
    2019: "1pN3fn2wY34GH6cY-gKfbxRJJBFE0lb_l", 2020: "1esu6IiH5TVTxFoedv6DBGDd01Gvi8785",
    2021: "12xH8LX9aN2gObR766YN3cMcuycwyCJDz", 2022: "1PRQjuV5gOn_nn6UNvaJyVURDIfbSAK4-",
    2023: "1-WO3SfNrwwZ5_l7fRTiwBKRw7mi1-HUq", 2024: "14lB0vqMFkaZj8HZ44b0njYgxs9nAN8KO",
    2025: "1-G3MdmHBt6CprDwcW99xxC4BZ2DU5ryR",
}
PRF_PESSOA = {
    2019: "14r_9zudjjndgcnjRddzD5lvn9MX5VvZZ", 2020: "1iQvs2D9a2XO9vIukrjEIIhtjzkNkgD7Z",
    2021: "15W_l07-6taOh8Ycn8uk2Er9PnSj0vq3f", 2022: "1sd8YIqIHapYaxQeaa-6yeWMdVLTl6hgD",
    2023: "1-Yk6TV00CH3PixTkKmkoUJQsNiUc5xLm", 2024: "14lVfqdoE2gxDliaKZu7K9Mx6847maPtl",
    2025: "1-Gp9S-ALO0D1nT8S_OKoC8xlW7BY8F82",
}
PRF_PESSOA_TODAS_CAUSAS = {
    2019: "1DAJYKVfkTcPhQodSmHp9rsG1Q8XJW-m3", 2020: "1yQtVOsAlupPHQVVTmbJo0NR3XMzgHANO",
    2021: "1Gk3U6cMOZIevsDZHLi6J503xoCRS_lnI", 2022: "1wskEgRC3ame7rncSDQ7qWhKsoKw1lohY",
    2023: "1-caam_dahYOf2eorq4mez04Om6DD5d_3", 2024: "14qBOhrE1gioVtuXgxkCJ9kCA8YtUGXKA",
    2025: "1-PJGRbfSe7PVjU37A3wTCls_NRXyVGRD",
}
PRF_INFRACOES = {
    2019: "1R5LiAULtB22HP0EkG8GSwzTTSAvbp35L", 2020: "1e9DfwTd4DlQ57Wl0zGx3pvBBTuq07sUW",
    2021: "1kgHHk0lurTuu4ZEn4Vhfo5W0ejOvDnZJ", 2022: "1-oY2e1W4cjmbZCgdcGnmPCIod4MFCSpg",
    2023: "106pwbYv84gCtLhhcbi0B_4qyUQxfH2n3", 2024: "156WEl9V3AiAbkcE1AJij6Sslqu_qLQs7",
    2025: "10nxiQR5tZcNp3Pg7f69ysv0dc87UGDHc",
}
FROTA = {
    2019: f"{GOV}/arquivos-senatran/estatisticas/renavam/2019/dezembro/frota_munic_modelo_dezembro_2019.xls",
    2020: f"{GOV}/arquivos-senatran/estatisticas/renavam/2020/dezembro/frota-reg-munic-tipo-modelo-07-dezembro2020.xls",
    2021: f"{GOV}/arquivos-senatran/estatisticas/renavam/2021/dezembro/frota-munic-modelo-dezembro-2021.xls",
    2022: f"{GOV}/arquivos-senatran/estatisticas/renavam/2022/dezembro/frota_munic_modelo_dezembro_2022.xls",
    2023: f"{GOV}/arquivos-senatran/estatisticas/renavam/2023/Dezembro/frota_munic_modelo_dezembro_2023.xls",
    2024: f"{GOV}/conteudo-Senatran/FrotapormunicipioetipoDezembro2024.xlsx",
    2025: f"{GOV}/conteudo-Senatran/arquivos-renavam-2025/FrotaporMunicipioetipoDEZEMBRO2025.xlsx",
}


def baixar(url, destino, extrair=False):
    """Baixa url para destino; se extrair=True, descompacta o zip na mesma pasta."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > 0:
        print(f"  já existe: {destino.relative_to(DADOS)}")
    else:
        print(f"  baixando: {destino.relative_to(DADOS)} ...", end=" ", flush=True)
        temporario = destino.with_suffix(destino.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(temporario, "wb") as f:
                origem = gzip.GzipFile(fileobj=resp) if resp.headers.get("Content-Encoding") == "gzip" else resp
                shutil.copyfileobj(origem, f, length=1 << 20)
        except Exception as erro:
            temporario.unlink(missing_ok=True)
            print(f"FALHOU ({erro})")
            return
        temporario.rename(destino)
        print(f"{destino.stat().st_size / 1e6:.1f} MB")
    if extrair:
        with zipfile.ZipFile(destino) as z:
            z.extractall(destino.parent)


def acidentes():
    pasta = DADOS / "prf"
    for ano in ANOS:
        baixar(DRIVE.format(PRF_OCORRENCIA[ano]), pasta / "acidentes_ocorrencia" / f"datatran{ano}.zip", True)
        baixar(DRIVE.format(PRF_PESSOA[ano]), pasta / "acidentes_pessoa" / f"acidentes{ano}.zip", True)
        baixar(DRIVE.format(PRF_PESSOA_TODAS_CAUSAS[ano]),
               pasta / "acidentes_pessoa_todas_causas" / f"acidentes{ano}_todas_causas.zip", True)


def infracoes():
    for ano in ANOS:
        baixar(DRIVE.format(PRF_INFRACOES[ano]), DADOS / "prf" / "infracoes" / f"infracoes_{ano}.zip")


def ibge():
    pasta = DADOS / "ibge"
    baixar("https://servicodados.ibge.gov.br/api/v1/localidades/municipios", pasta / "municipios_ibge.json")
    baixar("https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv",
           pasta / "municipios_latlong.csv")
    baixar("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
           "?formato=application/vnd.geo%2Bjson&intrarregiao=UF&qualidade=minima", pasta / "malha_uf.geojson")
    # Estimativas anuais (2022 e 2023 não têm estimativa; 2022 vem do Censo)
    for ano in (2019, 2020, 2021, 2024, 2025):
        baixar(f"https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/9324/p/{ano}", pasta / f"pop_estimada_{ano}.json")
    baixar("https://apisidra.ibge.gov.br/values/t/4709/n6/all/v/93/p/2022", pasta / "populacao_censo2022_municipios.json")


def frota():
    for ano, url in FROTA.items():
        extensao = url.rsplit(".", 1)[-1]
        baixar(f"{url}/@@download/file", DADOS / "senatran_frota" / f"frota_municipio_{ano}_12.{extensao}")


def inmet():
    for ano in ANOS:
        baixar(f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip", DADOS / "inmet" / f"inmet_{ano}.zip")


GRUPOS = {"acidentes": acidentes, "infracoes": infracoes, "ibge": ibge, "frota": frota, "inmet": inmet}

if __name__ == "__main__":
    for nome in sys.argv[1:] or GRUPOS:
        print(f"[{nome}]")
        GRUPOS[nome]()
