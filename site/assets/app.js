"use strict";

const COR = { morte: "#c4261d", neutro: "#7c848b", grade: "#d3d7d5", tinta: "#1d2124", suave: "#565d63" };
const SEXO = { Masculino: "#14805a", Feminino: "#d1860a" };
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const SEM_INFORMACAO = new Set(["Ignorado", "Não informado", "Não Informado"]);
const MINIMO_TAXA = 30;
const TIPOS = { uint8: Uint8Array, uint16: Uint16Array, uint32: Uint32Array, float32: Float32Array };

const $ = (id) => document.getElementById(id);
const inteiro = (n) => Math.round(n).toLocaleString("pt-BR");
const decimal = (n) => n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const taxa = (mortos, acidentes) => (acidentes ? (100 * mortos) / acidentes : 0);

let meta, col, filtro;

async function carregar() {
  if (!("DecompressionStream" in window)) {
    throw new Error("Este navegador é antigo demais para abrir o painel. Atualize-o e recarregue a página.");
  }
  const [respostaMeta, respostaDados] = await Promise.all([fetch("assets/meta.json"), fetch("assets/dados.bin.gz")]);
  if (!respostaMeta.ok || !respostaDados.ok) throw new Error("Os dados não foram encontrados. Recarregue a página.");
  meta = await respostaMeta.json();
  const fluxo = respostaDados.body.pipeThrough(new DecompressionStream("gzip"));
  const binario = await new Response(fluxo).arrayBuffer();
  col = {};
  for (const [nome, c] of Object.entries(meta.colunas)) col[nome] = new TIPOS[c.tipo](binario, c.offset, c.n);
}

/* ---------- Filtros ---------- */

function filtroInicial() {
  const q = new URLSearchParams(location.search);
  const anos = meta.anos;
  const ano = (nome, padrao) => (anos.includes(+q.get(nome)) ? +q.get(nome) : padrao);
  return {
    de: ano("de", anos[0]),
    ate: ano("ate", anos[anos.length - 1]),
    uf: meta.categorias.uf.indexOf(q.get("uf")),
    br: q.has("br") ? meta.brs.indexOf(+q.get("br")) : -1,
    fatais: q.get("fatais") === "1",
  };
}

function preencherFiltros() {
  const opcoes = (el, itens) => el.replaceChildren(...itens.map(([v, t]) => new Option(t, v)));
  const anos = meta.anos.map((a) => [a, a]);
  opcoes($("f-de"), anos);
  opcoes($("f-ate"), anos);
  opcoes($("f-uf"), [[-1, "Todas"], ...meta.categorias.uf.map((u, i) => [i, u])]);
  opcoes($("f-br"), [[-1, "Todas"], ...meta.brs.map((b, i) => [i, nomeBr(b)])]);
  $("filtros").addEventListener("change", lerFiltros);
  $("filtros").addEventListener("submit", (e) => e.preventDefault());
  $("limpar").addEventListener("click", () => {
    filtro = { de: meta.anos[0], ate: meta.anos[meta.anos.length - 1], uf: -1, br: -1, fatais: false };
    aplicar();
  });
}

function lerFiltros(evento) {
  filtro = {
    de: +$("f-de").value, ate: +$("f-ate").value,
    uf: +$("f-uf").value, br: +$("f-br").value, fatais: $("f-fatais").checked,
  };
  if (filtro.de > filtro.ate) {
    if (evento.target.id === "f-de") filtro.ate = filtro.de;
    else filtro.de = filtro.ate;
  }
  aplicar();
}

function aplicar() {
  $("f-de").value = filtro.de;
  $("f-ate").value = filtro.ate;
  $("f-uf").value = filtro.uf;
  $("f-br").value = filtro.br;
  $("f-fatais").checked = filtro.fatais;

  const q = new URLSearchParams();
  if (filtro.de !== meta.anos[0]) q.set("de", filtro.de);
  if (filtro.ate !== meta.anos[meta.anos.length - 1]) q.set("ate", filtro.ate);
  if (filtro.uf >= 0) q.set("uf", meta.categorias.uf[filtro.uf]);
  if (filtro.br >= 0) q.set("br", meta.brs[filtro.br]);
  if (filtro.fatais) q.set("fatais", "1");
  const busca = q.toString();
  history.replaceState(null, "", busca ? `?${busca}` : location.pathname);

  desenhar(agregar());
}

const nomeBr = (b) => (b === 0 ? "Não informada" : `BR-${String(b).padStart(3, "0")}`);

/* ---------- Agregação ---------- */

function agregar() {
  const c = meta.categorias;
  const nAnos = meta.anos.length;
  const contador = (n) => ({ a: new Float64Array(n), m: new Float64Array(n) });
  const r = {
    acidentes: 0, mortos: 0, graves: 0, leves: 0,
    ano: contador(nAnos), mensal: new Float64Array(nAnos * 12),
    calor: new Float64Array(7 * 24), hora: contador(24), mes: new Float64Array(12),
    uf: contador(c.uf.length), br: contador(meta.brs.length),
    causa: contador(c.causa.length), tipo: contador(c.tipo.length), clima: contador(c.clima.length),
    pista: contador(c.pista.length), solo: contador(c.solo.length),
    trechoM: new Float64Array(meta.trechos.length), trechoA: new Float64Array(meta.trechos.length),
    trechoG: new Float64Array(meta.trechos.length),
  };
  const de = filtro.de - meta.anos[0], ate = filtro.ate - meta.anos[0];
  const { uf, br, fatais } = filtro;
  const passa = new Uint8Array(meta.linhas);

  for (let i = 0; i < meta.linhas; i++) {
    const ano = col.ano[i];
    if (ano < de || ano > ate) continue;
    if (uf >= 0 && col.uf[i] !== uf) continue;
    if (br >= 0 && col.br[i] !== br) continue;
    const m = col.mortos[i];
    if (fatais && m === 0) continue;
    passa[i] = 1;

    r.acidentes++; r.mortos += m; r.graves += col.graves[i]; r.leves += col.leves[i];
    const soma = (k, indice) => { k.a[indice]++; k.m[indice] += m; };
    soma(r.ano, ano);
    r.mensal[ano * 12 + col.mes[i]] += m;
    r.calor[col.dia[i] * 24 + col.hora[i]]++;
    soma(r.hora, col.hora[i]);
    r.mes[col.mes[i]]++;
    soma(r.uf, col.uf[i]); soma(r.br, col.br[i]);
    soma(r.causa, col.causa[i]); soma(r.tipo, col.tipo[i]); soma(r.clima, col.clima[i]);
    soma(r.pista, col.pista[i]); soma(r.solo, col.solo[i]);
    const t = col.trecho[i];
    r.trechoM[t] += m; r.trechoA[t]++; r.trechoG[t] += col.graves[i];
  }

  r.mapa = { lat: [], lon: [], z: [] };
  for (let j = 0; j < col.mapa_linha.length; j++) {
    const linha = col.mapa_linha[j];
    if (passa[linha]) { r.mapa.lat.push(col.mapa_lat[j]); r.mapa.lon.push(col.mapa_lon[j]); r.mapa.z.push(col.mortos[linha]); }
  }

  const tabela = (prefixo, visitar) => {
    const n = col[`${prefixo}_n`];
    for (let j = 0; j < n.length; j++) {
      const ano = col[`${prefixo}_ano`][j];
      if (ano < de || ano > ate) continue;
      if (uf >= 0 && col[`${prefixo}_uf`][j] !== uf) continue;
      if (br >= 0 && col[`${prefixo}_br`][j] !== br) continue;
      if (fatais && !col[`${prefixo}_fatal`][j]) continue;
      visitar(j, n[j]);
    }
  };
  r.veiculo = new Float64Array(c.veiculo.length);
  tabela("veic", (j, n) => { r.veiculo[col.veic_veiculo[j]] += n; });
  r.papel = new Float64Array(c.papel.length);
  tabela("papel", (j, n) => { r.papel[col.papel_papel[j]] += n; });
  r.vitimas = c.sexo.map(() => new Float64Array(c.faixa.length));
  tabela("vit", (j, n) => { r.vitimas[col.vit_sexo_c[j]][col.vit_faixa[j]] += n; });
  return r;
}

/* ---------- Gráficos ---------- */

const CONFIG = { displayModeBar: false, responsive: true };

function base(extra = {}) {
  return {
    font: { family: "Overpass, Arial, sans-serif", size: 14, color: COR.tinta },
    separators: ",.",
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 8, r: 16, t: 12, b: 28 },
    barcornerradius: 3,
    bargap: 0.28,
    hoverlabel: { bgcolor: "#fff", bordercolor: COR.grade, font: { family: "Overpass, Arial, sans-serif", color: COR.tinta } },
    ...extra,
  };
}

const eixoValor = { gridcolor: COR.grade, zeroline: false, automargin: true, rangemode: "tozero", tickformat: ",d", fixedrange: true };
const eixoCategoria = { showgrid: false, zeroline: false, automargin: true, fixedrange: true, tickfont: { color: COR.suave } };

function plotar(id, dados, layout, config = CONFIG) {
  const el = $(id);
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", el.parentElement.querySelector("h3").textContent);
  Plotly.react(el, dados, layout, config);
}

function quebrar(texto, largura = 32) {
  const linhas = [];
  let atual = "";
  for (const palavra of texto.split(" ")) {
    if (atual && (atual + " " + palavra).length > largura) { linhas.push(atual); atual = palavra; }
    else atual = atual ? `${atual} ${palavra}` : palavra;
  }
  linhas.push(atual);
  return linhas.join("<br>");
}

/* Barras horizontais; `itens` já vem do maior para o menor. */
function barrasH(id, itens, { cor, formato = ",d", unidade = "", detalhe }) {
  const ordem = [...itens].reverse();
  plotar(id, [{
    type: "bar", orientation: "h",
    y: ordem.map((d) => quebrar(d.nome)), x: ordem.map((d) => d.valor),
    marker: { color: cor },
    text: ordem.map((d) => (formato === ",d" ? inteiro(d.valor) : decimal(d.valor))),
    textposition: "outside", cliponaxis: false, textfont: { color: COR.tinta },
    customdata: ordem.map((d) => (detalhe ? detalhe(d) : "")),
    hovertemplate: `<b>%{y}</b><br>%{x:${formato}}${unidade}%{customdata}<extra></extra>`,
  }], base({
    xaxis: { showgrid: false, zeroline: false, fixedrange: true, showticklabels: false, autorange: false, range: [0, Math.max(...itens.map((d) => d.valor), 1) * 1.2] },
    yaxis: { ...eixoCategoria, tickfont: { color: COR.tinta, size: 13 } },
    margin: { l: 8, r: 8, t: 4, b: 4 },
  }));
}

function ranking(nomes, k, limite, ordenar) {
  const itens = nomes.map((nome, i) => ({ nome, a: k.a[i], m: k.m[i], taxa: taxa(k.m[i], k.a[i]) }))
    .filter((d) => d.a > 0);
  return itens.sort(ordenar).slice(0, limite);
}

const porTaxa = (nomes, k, limite = 15) => ranking(nomes, k, 999, (x, y) => y.taxa - x.taxa)
  .filter((d) => d.a >= MINIMO_TAXA && !SEM_INFORMACAO.has(d.nome))
  .slice(0, limite)
  .map((d) => ({ ...d, valor: d.taxa }));

const detalheTaxa = (d) => `<br>${inteiro(d.m)} mortos em ${inteiro(d.a)} acidentes`;

function colunas(id, x, y, cor, unidade, { formato = ",d", tick } = {}) {
  plotar(id, [{
    type: "bar", x, y, marker: { color: cor },
    hovertemplate: `<b>%{x}</b><br>%{y:${formato}}${unidade}<extra></extra>`,
  }], base({
    xaxis: { ...eixoCategoria, type: "category", ...(tick || {}) },
    yaxis: { ...eixoValor, tickformat: formato },
  }));
}

function nota(id, texto) { $(id).textContent = texto; }

function desenhar(r) {
  const c = meta.categorias;

  // Placa
  $("kpi-mortos").textContent = inteiro(r.mortos);
  $("kpi-graves").textContent = inteiro(r.graves);
  $("kpi-leves").textContent = inteiro(r.leves);
  $("kpi-acidentes").textContent = inteiro(r.acidentes);
  $("kpi-letalidade").textContent = decimal(taxa(r.mortos, r.acidentes));
  const lugar = filtro.uf >= 0 ? c.uf[filtro.uf] : "Brasil";
  const periodo = filtro.de === filtro.ate ? `${filtro.de}` : `${filtro.de} a ${filtro.ate}`;
  const trecho = filtro.br >= 0 ? `${nomeBr(meta.brs[filtro.br])}, ` : "";
  $("escopo").textContent = `${trecho}${lugar}, ${periodo}${filtro.fatais ? ", só acidentes com mortos" : ""}`;
  const numero = $("escudo-numero");
  const comNumero = filtro.br >= 0 && meta.brs[filtro.br] !== 0;
  numero.textContent = comNumero ? String(meta.brs[filtro.br]).padStart(3, "0") : filtro.br >= 0 ? "?" : "todas";
  numero.setAttribute("font-size", comNumero ? "32" : "24");

  const vazio = r.acidentes === 0;
  $("paineis").hidden = vazio;
  $("aviso").hidden = !vazio;
  if (vazio) {
    $("aviso").textContent = "Nenhum acidente com esses filtros. Troque a UF ou a rodovia, ou use Limpar filtros.";
    return;
  }

  // Ano a ano
  const anosVisiveis = meta.anos.map((a, i) => ({ ano: String(a), i })).filter((d) => +d.ano >= filtro.de && +d.ano <= filtro.ate);
  const serie = (k) => anosVisiveis.map((d) => k[d.i]);
  colunas("g-mortos-ano", anosVisiveis.map((d) => d.ano), serie(r.ano.m), COR.morte, " mortos");
  colunas("g-acidentes-ano", anosVisiveis.map((d) => d.ano), serie(r.ano.a), COR.neutro, " acidentes");
  const variacao = (k) => {
    const v = serie(k);
    if (v.length < 2 || !v[0]) return "";
    const p = (100 * (v[v.length - 1] - v[0])) / v[0];
    const lado = p >= 0 ? "Alta" : "Queda";
    return `${lado} de ${decimal(Math.abs(p))}% entre ${filtro.de} e ${filtro.ate}`;
  };
  nota("n-anos", variacao(r.ano.m));
  nota("n-acidentes-ano", variacao(r.ano.a));

  const datas = [], rotulos = [], valores = [];
  anosVisiveis.forEach((d) => {
    for (let m = 0; m < 12; m++) {
      if (d.i * 12 + m >= r.mensal.length) continue;
      datas.push(`${d.ano}-${String(m + 1).padStart(2, "0")}-01`);
      rotulos.push(`${MESES[m]} de ${d.ano}`);
      valores.push(r.mensal[d.i * 12 + m]);
    }
  });
  plotar("g-mensal", [{
    type: "scatter", mode: "lines", x: datas, y: valores, customdata: rotulos,
    line: { color: COR.morte, width: 2 },
    hovertemplate: "<b>%{customdata}</b><br>%{y:,d} mortos<extra></extra>",
  }], base({ xaxis: { ...eixoCategoria, type: "date", tickformat: "%Y", dtick: "M12", ticklabelmode: "period" }, yaxis: eixoValor }));

  // Quando
  const z = meta.dias.map((_, d) => Array.from(r.calor.subarray(d * 24, d * 24 + 24)));
  plotar("g-calor", [{
    type: "heatmap", z, x: Array.from({ length: 24 }, (_, h) => `${h}h`), y: meta.dias,
    xgap: 2, ygap: 2, colorscale: [[0, "#e4efe9"], [1, "#0b5d3b"]],
    colorbar: { thickness: 10, outlinewidth: 0, tickformat: ",d", title: { text: "Acidentes", side: "right" } },
    hovertemplate: "<b>%{y} às %{x}</b><br>%{z:,d} acidentes<extra></extra>",
  }], base({
    xaxis: { ...eixoCategoria, type: "category", dtick: 3 },
    yaxis: { ...eixoCategoria, autorange: "reversed", tickfont: { color: COR.tinta } },
  }));
  let pico = 0;
  r.calor.forEach((v, i) => { if (v > r.calor[pico]) pico = i; });
  nota("n-calor", `Pico: ${meta.dias[Math.floor(pico / 24)].toLowerCase()} às ${pico % 24}h, com ${inteiro(r.calor[pico])} acidentes`);

  const horas = Array.from({ length: 24 }, (_, h) => h);
  const taxaHora = horas.map((h) => (r.hora.a[h] >= MINIMO_TAXA ? taxa(r.hora.m[h], r.hora.a[h]) : null));
  colunas("g-hora", horas.map((h) => `${h}h`), taxaHora, COR.morte, " mortos a cada 100 acidentes",
    { formato: ".1f", tick: { dtick: 3 } });
  const piorHora = horas.filter((h) => taxaHora[h] !== null).sort((a, b) => taxaHora[b] - taxaHora[a])[0];
  nota("n-hora", piorHora === undefined ? "" : `Horário mais letal: ${piorHora}h, com ${decimal(taxaHora[piorHora])} mortos a cada 100 acidentes`);

  colunas("g-sazonal", MESES, Array.from(r.mes), COR.neutro, " acidentes");
  const mesTopo = r.mes.indexOf(Math.max(...r.mes));
  nota("n-sazonal", `Mês com mais acidentes: ${MESES[mesTopo]}`);

  // Onde
  desenharMapa(r);
  const ufs = ranking(c.uf, r.uf, 15, (x, y) => y.m - x.m).filter((d) => d.m > 0).map((d) => ({ ...d, valor: d.m }));
  barrasH("g-uf", ufs, { cor: COR.morte, unidade: " mortos", detalhe: (d) => `<br>${inteiro(d.a)} acidentes` });
  nota("n-uf", ufs.length ? `${ufs[0].nome} lidera com ${inteiro(ufs[0].m)} mortos` : "");
  const brs = ranking(meta.brs.map(nomeBr), r.br, 999, (x, y) => y.m - x.m)
    .filter((d) => d.m > 0 && !SEM_INFORMACAO.has(d.nome) && d.nome !== "Não informada").slice(0, 15).map((d) => ({ ...d, valor: d.m }));
  barrasH("g-br", brs, { cor: COR.morte, unidade: " mortos", detalhe: (d) => `<br>${inteiro(d.a)} acidentes` });
  nota("n-br", brs.length ? `${brs[0].nome} lidera com ${inteiro(brs[0].m)} mortos` : "");

  const ordem = meta.trechos.map((_, i) => i)
    .filter((i) => r.trechoM[i] > 0 && meta.trechos[i].nome && !meta.trechos[i].nome.startsWith("BR-000"))
    .sort((a, b) => r.trechoM[b] - r.trechoM[a] || r.trechoA[b] - r.trechoA[a]).slice(0, 20);
  const celula = (texto, classe = "") => {
    const td = document.createElement("td");
    td.textContent = texto;
    td.className = classe;
    return td;
  };
  $("t-trechos").tBodies[0].replaceChildren(...ordem.map((i) => {
    const t = meta.trechos[i], tr = document.createElement("tr");
    tr.append(celula(t.nome), celula(t.uf), celula(t.municipio),
      celula(inteiro(r.trechoM[i]), "num mortos"), celula(inteiro(r.trechoA[i]), "num"), celula(inteiro(r.trechoG[i]), "num"));
    return tr;
  }));

  // Por quê
  const causas = ranking(c.causa, r.causa, 15, (x, y) => y.a - x.a).filter((d) => !SEM_INFORMACAO.has(d.nome)).map((d) => ({ ...d, valor: d.a }));
  barrasH("g-causa", causas, { cor: COR.neutro, unidade: " acidentes", detalhe: (d) => `<br>${inteiro(d.m)} mortos, ${decimal(d.taxa)} a cada 100 acidentes` });
  nota("n-causa", causas.length ? `A mais frequente: ${causas[0].nome.toLowerCase()}` : "");
  const tipos = porTaxa(c.tipo, r.tipo);
  barrasH("g-tipo", tipos, { cor: COR.morte, formato: ".1f", detalhe: detalheTaxa });
  nota("n-tipo", tipos.length ? `O mais letal: ${tipos[0].nome.toLowerCase()}` : "");
  const climas = porTaxa(c.clima, r.clima);
  barrasH("g-clima", climas, { cor: COR.morte, formato: ".1f", detalhe: detalheTaxa });
  nota("n-clima", climas.length ? `O mais letal: ${climas[0].nome.toLowerCase()}` : "");
  barrasH("g-pista", porTaxa(c.pista, r.pista), { cor: COR.morte, formato: ".1f", detalhe: detalheTaxa });
  const nomesSolo = c.solo.map((s) => (s === "Sim" ? "Área urbana" : "Área rural"));
  barrasH("g-solo", porTaxa(nomesSolo, r.solo), { cor: COR.morte, formato: ".1f", detalhe: detalheTaxa });

  // Quem
  const veiculos = c.veiculo.map((nome, i) => ({ nome, valor: r.veiculo[i] }))
    .filter((d) => d.valor > 0 && !SEM_INFORMACAO.has(d.nome)).sort((x, y) => y.valor - x.valor).slice(0, 12);
  barrasH("g-veiculo", veiculos, { cor: COR.morte, unidade: " mortos" });
  nota("n-veiculo", veiculos.length ? `Mais mortes em: ${veiculos[0].nome.toLowerCase()}` : "");
  const papeis = c.papel.map((nome, i) => ({ nome, valor: r.papel[i] })).filter((d) => d.valor > 0).sort((x, y) => y.valor - x.valor);
  barrasH("g-papel", papeis, { cor: COR.neutro, unidade: " pessoas" });

  plotar("g-vitimas", c.sexo.map((sexo, s) => ({
    type: "bar", name: sexo, x: c.faixa, y: Array.from(r.vitimas[s]), marker: { color: SEXO[sexo] },
    hovertemplate: `<b>${sexo}, %{x} anos</b><br>%{y:,d} vítimas<extra></extra>`,
  })), base({
    barmode: "group", bargroupgap: 0.06,
    legend: { orientation: "h", x: 0, y: 1.12 },
    xaxis: { ...eixoCategoria, type: "category" }, yaxis: eixoValor,
    margin: { l: 8, r: 16, t: 32, b: 28 },
  }));
  const total = r.vitimas.map((f) => f.reduce((s, v) => s + v, 0));
  const soma = total[0] + total[1];
  nota("n-vitimas", soma ? `Homens são ${decimal((100 * total[0]) / soma)}% das vítimas com sexo informado` : "");
}

function desenharMapa(r) {
  nota("n-mapa", `${inteiro(r.mapa.lat.length)} acidentes com mortos. Use os botões + e − para aproximar.`);
  try {
    plotar("g-mapa", [{
      type: "densitymap", lat: r.mapa.lat, lon: r.mapa.lon, z: r.mapa.z, radius: 7,
      colorscale: [[0, "rgba(196,38,29,0)"], [0.25, "rgba(196,38,29,.45)"], [1, "#7a120b"]],
      showscale: false, hoverinfo: "skip",
    }], base({
      margin: { l: 0, r: 0, t: 0, b: 0 }, uirevision: "mapa",
      map: { style: "carto-positron", center: { lat: -15, lon: -52 }, zoom: 3.2 },
    }), { responsive: true, displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ["toImage"] });
  } catch (erro) {
    nota("n-mapa", "O mapa precisa de WebGL, que está desligado neste navegador.");
  }
}

/* ---------- Início ---------- */

carregar().then(() => {
  preencherFiltros();
  filtro = filtroInicial();
  aplicar();
}).catch((erro) => {
  $("escopo").textContent = "Os dados não carregaram";
  $("paineis").hidden = true;
  $("aviso").hidden = false;
  $("aviso").textContent = erro.message;
});
