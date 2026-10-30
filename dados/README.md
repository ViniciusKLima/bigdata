# dados/

Os dados não ficam no repositório (passam de 3 GB). Para baixar tudo:

```
python src/baixar_dados.py
python src/etl_prf_acidentes.py
```

| Pasta | Conteúdo | Fonte |
|---|---|---|
| `prf/acidentes_ocorrencia/` | 1 linha por acidente, 2019–2025 | [PRF – Dados Abertos](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf) |
| `prf/acidentes_pessoa/` | 1 linha por pessoa envolvida | PRF |
| `prf/acidentes_pessoa_todas_causas/` | pessoa × causa × tipo de acidente | PRF |
| `prf/infracoes/` | multas aplicadas nas rodovias federais (ZIP) | PRF |
| `ibge/` | municípios, coordenadas, população, mapa das UFs | [IBGE](https://servicodados.ibge.gov.br/api/docs) |
| `senatran_frota/` | frota de veículos por município (dezembro de cada ano) | [SENATRAN](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran) |
| `inmet/` | estações meteorológicas automáticas | [INMET](https://portal.inmet.gov.br/dadoshistoricos) — se o download automático falhar, baixe pelo navegador |
| `processado/` | Parquet tratado, gerado pelo ETL | — |
