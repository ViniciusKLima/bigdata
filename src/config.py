"""Caminhos centrais do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"

# Camada bruta (arquivos como vieram da fonte)
PRF_OCORRENCIAS = DADOS / "prf" / "acidentes_ocorrencia"
PRF_PESSOAS = DADOS / "prf" / "acidentes_pessoa"

# Camada tratada (Parquet, pronta para análise)
PROCESSADO = DADOS / "processado"
ACIDENTES_PARQUET = PROCESSADO / "acidentes.parquet"
PESSOAS_PARQUET = PROCESSADO / "pessoas.parquet"
