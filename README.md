# Acidentes nas Rodovias Federais — Projeto de Big Data

Análise dos acidentes de trânsito nas rodovias federais brasileiras (2019–2025) a partir dos
dados abertos da Polícia Rodoviária Federal, cruzados com infrações, população, frota e clima.

**Pergunta central:** quando, onde e por que acontecem os acidentes mais graves — e a
fiscalização está onde as pessoas morrem?

**Painel online:** https://viniciusklima.github.io/bigdata/

## Números iniciais (2019–2025)

- 473.813 acidentes
- 39.303 mortos
- 8,3 mortos a cada 100 acidentes

## Arquitetura

```
Fontes abertas ──► dados brutos (CSV/ZIP) ──► ETL em Python ──► Parquet ──► Dashboard
PRF, IBGE,          dados/prf, ibge, ...        src/              dados/       app/ (Streamlit)
SENATRAN, INMET                                                   processado/  BIGDATA.pbix (Power BI)
```

A evolução prevista (ver `docs/projeto_big_data_trafego_completo.pdf`) usa Kafka para ingestão
em fluxo, Spark para processamento e PostgreSQL como camada de consumo do Power BI.

## Como rodar

Requer Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python src/baixar_dados.py        # baixa as fontes (~3 GB)
python src/etl_prf_acidentes.py   # trata e gera os arquivos Parquet (~35 s)
streamlit run app/dashboard.py    # abre o dashboard em http://localhost:8501
```

## Site (GitHub Pages)

O Pages só serve arquivos estáticos, então o Streamlit não roda lá. O Python gera os dados
compactados e o navegador filtra e desenha. Para atualizar o site:

```bash
python src/gerar_site.py                              # recria site/assets/dados.bin.gz e meta.json
git add site && git commit -m "Atualiza dados do site"
git push origin main
git push origin `git subtree split --prefix site main`:gh-pages --force
```

## Estrutura

```
app/dashboard.py            dashboard interativo (Streamlit + Plotly)
src/config.py               caminhos do projeto
src/baixar_dados.py         download das fontes de dados
src/etl_prf_acidentes.py    limpeza e padronização dos acidentes -> Parquet
src/gerar_site.py           gera os dados compactos do site estático
site/                       site publicado no GitHub Pages
dados/                      dados brutos e tratados (fora do Git, ver dados/README.md)
docs/                       documentação do projeto
BIGDATA.pbix                relatório Power BI
```

## Dashboard

Filtros por período, UF, BR e acidentes fatais, com as abas:

- **Visão geral** — totais, evolução anual e mensal, gravidade
- **Quando** — mapa de calor dia × hora, letalidade por hora, sazonalidade
- **Onde** — mapa de concentração de mortes, ranking por UF e BR, trechos de 10 km mais letais
- **Por quê** — causas, tipos de acidente, clima, tipo de pista, urbano × rural
- **Quem** — tipo de veículo, papel do envolvido, faixa etária e sexo das vítimas

## Fontes

- [PRF — Dados Abertos](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf)
- [IBGE — API de dados](https://servicodados.ibge.gov.br/api/docs)
- [SENATRAN — Frota de veículos](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran)
- [INMET — Dados históricos](https://portal.inmet.gov.br/dadoshistoricos)
