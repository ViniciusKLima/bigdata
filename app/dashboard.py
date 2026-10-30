"""Dashboard exploratório dos acidentes nas rodovias federais (PRF).

Uso:
    streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from config import ACIDENTES_PARQUET, PESSOAS_PARQUET  # noqa: E402

st.set_page_config(page_title="Acidentes nas Rodovias Federais", page_icon="🚧", layout="wide")

COR = "#C0392B"
ESCALA = "Reds"
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


@st.cache_data
def carregar():
    acidentes = pd.read_parquet(ACIDENTES_PARQUET)
    pessoas = pd.read_parquet(
        PESSOAS_PARQUET,
        columns=["id", "ano", "uf", "br", "tipo_veiculo", "tipo_envolvido",
                 "estado_fisico", "idade", "faixa_etaria", "sexo"],
    )
    return acidentes, pessoas


def letalidade(df):
    """Mortos a cada 100 acidentes."""
    return 100 * df["mortos"].sum() / max(len(df), 1)


def barras_h(df, x, y, titulo, **kw):
    fig = px.bar(df, x=x, y=y, orientation="h", title=titulo, color_discrete_sequence=[COR], **kw)
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title=None, height=420)
    return fig


acidentes, pessoas = carregar()

# ---------------- Filtros ----------------
st.sidebar.header("Filtros")
anos = sorted(acidentes["ano"].dropna().unique())
faixa_anos = st.sidebar.select_slider("Período", options=anos, value=(anos[0], anos[-1]))
ufs = st.sidebar.multiselect("UF", sorted(acidentes["uf"].dropna().unique()))
brs = st.sidebar.multiselect("BR", sorted(acidentes["br"].dropna().unique()))
so_fatais = st.sidebar.checkbox("Somente acidentes com mortos")

filtro = acidentes["ano"].between(*faixa_anos)
if ufs:
    filtro &= acidentes["uf"].isin(ufs)
if brs:
    filtro &= acidentes["br"].isin(brs)
if so_fatais:
    filtro &= acidentes["fatal"]
df = acidentes[filtro]
pes = pessoas[pessoas["id"].isin(df["id"])]

st.sidebar.caption(f"Fonte: PRF – Dados Abertos. {len(acidentes):,} acidentes de 2019 a 2025.".replace(",", "."))

# ---------------- Cabeçalho e KPIs ----------------
st.title("🚧 Acidentes nas Rodovias Federais")
st.caption(f"{faixa_anos[0]}–{faixa_anos[1]}" + (f" · UF: {', '.join(ufs)}" if ufs else "")
           + (f" · BR: {', '.join(map(str, brs))}" if brs else ""))

fmt = lambda n: f"{int(n):,}".replace(",", ".")  # noqa: E731
k = st.columns(5)
k[0].metric("Acidentes", fmt(len(df)))
k[1].metric("Mortos", fmt(df["mortos"].sum()))
k[2].metric("Feridos graves", fmt(df["feridos_graves"].sum()))
k[3].metric("Feridos leves", fmt(df["feridos_leves"].sum()))
k[4].metric("Mortos / 100 acidentes", f"{letalidade(df):.1f}".replace(".", ","))

aba_geral, aba_quando, aba_onde, aba_porque, aba_quem = st.tabs(
    ["📈 Visão geral", "🕒 Quando", "📍 Onde", "❓ Por quê", "👥 Quem"]
)

# ---------------- Visão geral ----------------
with aba_geral:
    c1, c2 = st.columns(2)
    por_ano = df.groupby("ano").agg(acidentes=("id", "size"), mortos=("mortos", "sum")).reset_index()
    fig = px.bar(por_ano, x="ano", y="acidentes", title="Acidentes por ano",
                 color_discrete_sequence=["#7F8C8D"], text_auto=True)
    c1.plotly_chart(fig, width="stretch")
    fig = px.line(por_ano, x="ano", y="mortos", markers=True, title="Mortos por ano",
                  color_discrete_sequence=[COR])
    c2.plotly_chart(fig, width="stretch")

    mensal = df.set_index("data").resample("MS").agg({"id": "size", "mortos": "sum"}).reset_index()
    mensal.columns = ["mes", "acidentes", "mortos"]
    fig = px.line(mensal, x="mes", y=["acidentes", "mortos"], title="Evolução mensal",
                  color_discrete_sequence=["#7F8C8D", COR])
    fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

    gravidade = df["classificacao_acidente"].value_counts().reset_index()
    fig = px.pie(gravidade, names="classificacao_acidente", values="count", hole=0.55,
                 title="Classificação dos acidentes",
                 color_discrete_sequence=["#BDC3C7", "#E67E22", COR, "#95A5A6"])
    st.plotly_chart(fig, width="stretch")

# ---------------- Quando ----------------
with aba_quando:
    mapa_calor = df.pivot_table(index="dia_semana", columns="hora", values="id",
                                aggfunc="size", observed=False).fillna(0)
    fig = px.imshow(mapa_calor, color_continuous_scale=ESCALA, aspect="auto",
                    title="Acidentes por dia da semana e hora",
                    labels={"x": "Hora", "y": "", "color": "Acidentes"})
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    por_hora = df.groupby("hora").apply(
        lambda g: pd.Series({"acidentes": len(g), "letalidade": letalidade(g)}), include_groups=False
    ).reset_index()
    fig = px.bar(por_hora, x="hora", y="letalidade", title="Mortos a cada 100 acidentes, por hora",
                 color="letalidade", color_continuous_scale=ESCALA)
    fig.update_layout(coloraxis_showscale=False)
    c1.plotly_chart(fig, width="stretch")

    por_mes = df.groupby("mes").size().reindex(range(1, 13)).reset_index(name="acidentes")
    por_mes["mes"] = MESES
    fig = px.bar(por_mes, x="mes", y="acidentes", title="Acidentes por mês (sazonalidade)",
                 color_discrete_sequence=["#7F8C8D"])
    c2.plotly_chart(fig, width="stretch")

    fase = df.groupby("fase_dia").apply(
        lambda g: pd.Series({"acidentes": len(g), "letalidade": letalidade(g)}), include_groups=False
    ).reset_index()
    fig = px.bar(fase, x="fase_dia", y=["acidentes"], title="Acidentes por fase do dia",
                 color_discrete_sequence=["#7F8C8D"], text_auto=True)
    st.plotly_chart(fig, width="stretch")

# ---------------- Onde ----------------
with aba_onde:
    fatais = df[df["fatal"] & df["latitude"].notna()]
    fig = px.density_map(fatais, lat="latitude", lon="longitude", z="mortos", radius=6,
                         center={"lat": -15.0, "lon": -52.0}, zoom=3.3, map_style="carto-positron",
                         color_continuous_scale=ESCALA, height=620,
                         title=f"Concentração de mortes ({fmt(len(fatais))} acidentes fatais)")
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    por_uf = df.groupby("uf").agg(acidentes=("id", "size"), mortos=("mortos", "sum")).reset_index()
    c1.plotly_chart(barras_h(por_uf.nlargest(15, "mortos"), "mortos", "uf", "Mortos por UF (top 15)"),
                    width="stretch")
    por_br = df.groupby("br").agg(mortos=("mortos", "sum")).reset_index()
    por_br["br"] = "BR-" + por_br["br"].astype(str).str.zfill(3)
    c2.plotly_chart(barras_h(por_br.nlargest(15, "mortos"), "mortos", "br", "Mortos por rodovia (top 15)"),
                    width="stretch")

    st.subheader("Trechos de 10 km mais letais")
    trechos = (df.dropna(subset=["trecho"])
               .groupby(["trecho", "uf"])
               .agg(acidentes=("id", "size"), mortos=("mortos", "sum"),
                    feridos_graves=("feridos_graves", "sum"),
                    municipio=("municipio", lambda s: s.mode().iat[0]))
               .reset_index().nlargest(20, "mortos"))
    st.dataframe(trechos, hide_index=True, width="stretch")

# ---------------- Por quê ----------------
with aba_porque:
    def resumo(col, n=15):
        g = df.groupby(col).apply(
            lambda x: pd.Series({"acidentes": len(x), "mortos": x["mortos"].sum(),
                                 "letalidade": letalidade(x)}), include_groups=False
        ).reset_index()
        return g[g["acidentes"] >= 100].nlargest(n, "acidentes")

    causas = resumo("causa_acidente")
    st.plotly_chart(barras_h(causas, "acidentes", "causa_acidente", "Principais causas (por nº de acidentes)",
                             hover_data=["mortos", "letalidade"]), width="stretch")

    c1, c2 = st.columns(2)
    tipos = resumo("tipo_acidente")
    fig = px.scatter(tipos, x="acidentes", y="letalidade", size="mortos", text="tipo_acidente",
                     title="Tipo de acidente: frequência × letalidade", color_discrete_sequence=[COR])
    fig.update_traces(textposition="top center", textfont_size=10)
    c1.plotly_chart(fig, width="stretch")

    clima = resumo("condicao_meteorologica")
    c2.plotly_chart(barras_h(clima, "letalidade", "condicao_meteorologica",
                             "Mortos / 100 acidentes por condição do tempo",
                             hover_data=["acidentes", "mortos"]), width="stretch")

    c1, c2 = st.columns(2)
    tracado = resumo("tipo_pista")
    c1.plotly_chart(barras_h(tracado, "letalidade", "tipo_pista", "Letalidade por tipo de pista",
                             hover_data=["acidentes"]), width="stretch")
    solo = resumo("uso_solo")
    solo["uso_solo"] = solo["uso_solo"].map({"Sim": "Área urbana", "Não": "Área rural"})
    c2.plotly_chart(barras_h(solo, "letalidade", "uso_solo", "Letalidade: urbano × rural",
                             hover_data=["acidentes"]), width="stretch")

# ---------------- Quem ----------------
with aba_quem:
    c1, c2 = st.columns(2)
    veic = pes.groupby("tipo_veiculo").agg(
        envolvidos=("id", "size"), mortos=("estado_fisico", lambda s: (s == "Óbito").sum())
    ).reset_index()
    c1.plotly_chart(barras_h(veic.nlargest(12, "mortos"), "mortos", "tipo_veiculo",
                             "Mortos por tipo de veículo"), width="stretch")

    envolvido = pes["tipo_envolvido"].value_counts().reset_index()
    fig = px.pie(envolvido, names="tipo_envolvido", values="count", hole=0.55,
                 title="Papel dos envolvidos", color_discrete_sequence=px.colors.sequential.Reds_r)
    c2.plotly_chart(fig, width="stretch")

    vitimas = pes[pes["estado_fisico"].isin(["Óbito", "Lesões Graves"])
                  & pes["sexo"].isin(["Masculino", "Feminino"])]
    piramide = vitimas.groupby(["faixa_etaria", "sexo"], observed=False).size().reset_index(name="vitimas")
    fig = px.bar(piramide, x="faixa_etaria", y="vitimas", color="sexo", barmode="group",
                 title="Mortos e feridos graves por faixa etária e sexo",
                 color_discrete_map={"Masculino": "#2C3E50", "Feminino": COR})
    st.plotly_chart(fig, width="stretch")
