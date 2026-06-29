import os
import sys
from datetime import date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from html import escape

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashboard.dashboard_repository import (
    buscar_total_processos,
    buscar_processos_monitorados,
    buscar_processos_sem_robo,
    buscar_total_orgaos,
    buscar_processos_por_status,
    buscar_ranking_orgaos,
    buscar_ultimas_movimentacoes,
    buscar_orgaos_sem_robo,
    buscar_ultimas_consultas,
    buscar_total_movimentacoes_recentes,
    buscar_movimentacoes_hoje_por_orgao,
    buscar_detalhe_movimentacoes_hoje,
    buscar_movimentacoes_do_dia_agrupadas,
    buscar_ultimas_movimentacoes_todos_processos,
    buscar_historico_7_dias,
    buscar_processo_por_id_dashboard,
    buscar_movimentacoes_do_processo,
    buscar_historico_consultas_do_processo,
)

from dashboard.dashboard_html import gerar_linhas_tabela

HOST = os.getenv("DASHBOARD_HOST", "localhost")
PORTA = int(os.getenv("DASHBOARD_PORT", "8000"))

# ─────────────────────────────────────────────
# CSS compartilhado
# ─────────────────────────────────────────────
CSS_BASE = """
    * { box-sizing: border-box; }
    body {
        font-family: Arial, sans-serif;
        background: #f4f6f8;
        margin: 0;
        padding: 24px;
        color: #111827;
    }
    h1 { margin-bottom: 5px; font-size: 32px; }
    h2 { margin-top: 0; }
    .subtitulo { color: #6b7280; margin-bottom: 25px; }
    .btn {
        display: inline-block;
        padding: 10px 18px;
        margin-bottom: 15px;
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        text-decoration: none;
        font-size: 14px;
    }
    .btn:hover { background: #1d4ed8; }
    .btn.secundario { background: #6b7280; }
    .btn.secundario:hover { background: #4b5563; }
    .cards {
        display: grid;
        grid-template-columns: repeat(4, minmax(180px, 1fr));
        gap: 18px;
        margin-bottom: 25px;
    }
    .card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 5px solid #2563eb;
        text-decoration: none;
        color: inherit;
        display: block;
        transition: box-shadow .15s;
    }
    .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
    .card.alerta { border-left-color: #f97316; }
    .card.alerta:hover { border-left-color: #ea580c; }
    .card.sucesso { border-left-color: #16a34a; }
    .card.neutro  { border-left-color: #6b7280; }
    .card h2 { margin: 0; font-size: 34px; color: #0f172a; }
    .card p  { margin: 6px 0 0; color: #6b7280; font-size: 14px; }
    .card .hint { font-size: 12px; color: #9ca3af; margin-top: 4px; }
    .grid-duplo {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-bottom: 25px;
    }
    section {
        background: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        overflow-x: auto;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td {
        border-bottom: 1px solid #e5e7eb;
        padding: 10px;
        text-align: left;
        font-size: 14px;
        vertical-align: top;
        max-width: 320px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    th { background: #f8fafc; color: #374151; }
    tr:hover td { background: #f9fafb; }
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge.verde   { background: #dcfce7; color: #166534; }
    .badge.cinza   { background: #f3f4f6; color: #4b5563; }
    .badge.azul    { background: #dbeafe; color: #1e40af; }
    .badge.laranja { background: #ffedd5; color: #9a3412; }
    .badge.roxo    { background: #ede9fe; color: #5b21b6; }
    .barra-container { background: #e5e7eb; border-radius: 4px; height: 8px; width: 100%; }
    .barra { background: #f97316; height: 8px; border-radius: 4px; }
    .vazio { text-align: center; color: #6b7280; padding: 20px; }
    .footer { text-align: center; color: #777; margin-top: 30px; font-size: 13px; }
    /* Calendário 7 dias */
    .cal-semana {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    .cal-dia {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: white;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        min-width: 80px;
        text-decoration: none;
        color: inherit;
        border: 2px solid transparent;
        transition: border-color .15s, box-shadow .15s;
    }
    .cal-dia:hover { border-color: #f97316; box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
    .cal-dia.hoje { border-color: #2563eb; }
    .cal-dia.sem-dados { opacity: .55; }
    .cal-dia .dia-semana { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; }
    .cal-dia .dia-num   { font-size: 20px; font-weight: 700; color: #111827; line-height: 1.2; }
    .cal-dia .dia-total { font-size: 22px; font-weight: 800; color: #f97316; margin-top: 4px; }
    .cal-dia .dia-label { font-size: 11px; color: #9ca3af; }
    .cal-dia .bolinha   { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; background: #e5e7eb; }
    .cal-dia.com-dados .bolinha { background: #f97316; }
    /* Navegação de datas */
    .nav-data {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }
    .nav-data a, .nav-data button {
        padding: 8px 16px;
        border-radius: 8px;
        border: 1px solid #d1d5db;
        background: white;
        cursor: pointer;
        font-size: 14px;
        text-decoration: none;
        color: #374151;
        transition: background .1s;
    }
    .nav-data a:hover, .nav-data button:hover { background: #f3f4f6; }
    .nav-data .data-atual {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
    }
    .nav-data input[type=date] {
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #d1d5db;
        font-size: 14px;
        cursor: pointer;
    }
    @media (max-width: 1000px) {
        .cards { grid-template-columns: repeat(2, 1fr); }
        .grid-duplo { grid-template-columns: 1fr; }
    }
    @media (max-width: 600px) {
        .cards { grid-template-columns: 1fr; }
        body { padding: 12px; }
    }
"""


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _badge_status(status):
    s = (status or "").lower()
    if "finalizado" in s or "deferido" in s or "encerrado" in s:
        return f'<span class="badge verde">{escape(status or "")}</span>'
    if "análise" in s or "andamento" in s:
        return f'<span class="badge azul">{escape(status or "")}</span>'
    if "indeferido" in s:
        return f'<span class="badge laranja">{escape(status or "")}</span>'
    return f'<span class="badge cinza">{escape(status or "Sem status")}</span>'


def _nav(pagina_atual="/"):
    links = [
        ("/", "🏠 Dashboard"),
        ("/movimentacoes-hoje", "📋 Movimentações Hoje"),
    ]
    html = '<nav style="margin-bottom:20px;display:flex;gap:10px;flex-wrap:wrap;">'
    for href, label in links:
        estilo = "btn" if href != pagina_atual else "btn secundario"
        html += f'<a href="{href}" class="{estilo}">{escape(label)}</a>'
    html += "</nav>"
    return html


# ─────────────────────────────────────────────
# PÁGINA PRINCIPAL — Dashboard
# ─────────────────────────────────────────────
def _gerar_calendario_7_dias(historico):
    """Gera os 7 cards do mini-calendário com links para cada dia."""
    # Monta dict data → dados para lookup rápido
    por_dia = {}
    for row in historico:
        d = row.get("dia")
        if d:
            por_dia[str(d)] = row

    hoje = date.today()
    dias_semana_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    html = '<div class="cal-semana">'

    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        chave = str(dia)
        dados = por_dia.get(chave, {})
        total = dados.get("total_processos", 0)
        nome_dia = dias_semana_pt[dia.weekday()]
        is_hoje = dia == hoje
        tem_dados = total > 0

        cls = "cal-dia"
        if is_hoje:
            cls += " hoje"
        if tem_dados:
            cls += " com-dados"
        else:
            cls += " sem-dados"

        link = f"/movimentacoes-hoje?data={chave}"
        label_dia = "hoje" if is_hoje else dia.strftime("%d/%m")

        html += f"""
        <a href="{link}" class="{cls}" title="Ver {label_dia}">
            <span class="dia-semana">{nome_dia}</span>
            <span class="dia-num">{dia.day:02d}</span>
            <span class="dia-total">{total if tem_dados else '—'}</span>
            <span class="dia-label">{'processo' + ('s' if total != 1 else '') if tem_dados else 'sem mov.'}</span>
            <span class="bolinha"></span>
        </a>"""

    html += "</div>"
    return html


def gerar_html_dashboard():
    total_processos       = buscar_total_processos()
    processos_monitorados = buscar_processos_monitorados()
    total_orgaos          = buscar_total_orgaos()
    novas_movimentacoes   = buscar_total_movimentacoes_recentes()
    processos_por_status  = buscar_processos_por_status()
    ranking_orgaos        = buscar_ranking_orgaos()
    ultimas_movimentacoes = buscar_ultimas_movimentacoes()
    orgaos_sem_robo       = buscar_orgaos_sem_robo()
    ultimas_consultas     = buscar_ultimas_consultas()
    mov_por_orgao         = buscar_movimentacoes_hoje_por_orgao()
    historico_7           = buscar_historico_7_dias()

    # Linhas da tabela de status com badges
    html_status = ""
    for item in processos_por_status:
        s = escape(str(item.get("status") or ""))
        t = item.get("total", 0)
        html_status += f"<tr><td>{_badge_status(s)}</td><td><strong>{t}</strong></td></tr>"
    if not html_status:
        html_status = '<tr><td colspan="2" class="vazio">Sem dados</td></tr>'

    html_ranking = gerar_linhas_tabela(ranking_orgaos, ["orgao", "total_processos"])

    html_movimentacoes = ""
    for m in ultimas_movimentacoes:
        html_movimentacoes += (
            f"<tr>"
            f"<td>{escape(str(m.get('numero_processo') or ''))}</td>"
            f"<td>{escape(str(m.get('empresa') or ''))}</td>"
            f"<td>{escape(str(m.get('orgao') or ''))}</td>"
            f"<td>{escape(str(m.get('data_movimento') or ''))}</td>"
            f"<td>{escape(str(m.get('descricao') or ''))}</td>"
            f"</tr>"
        )
    if not html_movimentacoes:
        html_movimentacoes = '<tr><td colspan="5" class="vazio">Nenhuma movimentação recente</td></tr>'

    html_orgaos_sem_robo = gerar_linhas_tabela(orgaos_sem_robo, ["nome", "total_processos", "url"])

    html_consultas = ""
    for c in ultimas_consultas:
        sc = str(c.get("status_consulta") or "")
        badge = _badge_status(sc) if sc == "OK" else f'<span class="badge laranja">{escape(sc)}</span>'
        html_consultas += (
            f"<tr>"
            f"<td>{escape(str(c.get('numero_processo') or ''))}</td>"
            f"<td>{escape(str(c.get('empresa') or ''))}</td>"
            f"<td>{escape(str(c.get('orgao') or ''))}</td>"
            f"<td>{badge}</td>"
            f"<td>{escape(str(c.get('data_consulta') or ''))}</td>"
            f"</tr>"
        )
    if not html_consultas:
        html_consultas = '<tr><td colspan="5" class="vazio">Nenhuma consulta registrada</td></tr>'

    # Mini breakdown de movimentações por prefeitura no card
    mini_lista = ""
    if mov_por_orgao:
        for item in mov_por_orgao[:4]:
            orgao = escape(str(item.get("orgao") or ""))
            total = item.get("total_processos", 0)
            mini_lista += f'<div style="font-size:12px;color:#6b7280;margin-top:3px;">• {orgao}: <strong>{total}</strong></div>'
    else:
        mini_lista = '<div style="font-size:12px;color:#9ca3af;margin-top:4px;">Nenhuma hoje</div>'

    html_calendario = _gerar_calendario_7_dias(historico_7)

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>SSA Monitor Processos</title>
    <style>{CSS_BASE}</style>
</head>
<body>
    <h1>SSA Monitor Processos</h1>
    <div class="subtitulo">Dashboard gerencial · atualiza a cada 30s</div>
    {_nav("/")}

    <div class="cards">
        <div class="card">
            <h2>{total_processos}</h2>
            <p>Total de processos</p>
        </div>
        <div class="card sucesso">
            <h2>{processos_monitorados}</h2>
            <p>Processos monitorados</p>
        </div>
        <a href="/movimentacoes-hoje" class="card alerta">
            <h2>{novas_movimentacoes}</h2>
            <p>Processos com mov. hoje</p>
            {mini_lista}
            <div class="hint">Clique para ver detalhes ›</div>
        </a>
        <div class="card neutro">
            <h2>{total_orgaos}</h2>
            <p>Total de órgãos/links</p>
        </div>
    </div>

    <section>
        <h2>Histórico dos últimos 7 dias</h2>
        <p style="font-size:13px;color:#6b7280;margin-top:0;margin-bottom:14px;">
            Clique em qualquer dia para ver os detalhes dos processos com movimentação.
        </p>
        {html_calendario}
    </section>

    <div class="grid-duplo">
        <section>
            <h2>Processos por status</h2>
            <table>
                <thead><tr><th>Status</th><th>Total</th></tr></thead>
                <tbody>{html_status}</tbody>
            </table>
        </section>
        <section>
            <h2>Ranking por prefeitura</h2>
            <table>
                <thead><tr><th>Prefeitura</th><th>Total de processos</th></tr></thead>
                <tbody>{html_ranking}</tbody>
            </table>
        </section>
    </div>

    <section>
        <h2>Últimas movimentações registradas</h2>
        <table>
            <thead>
                <tr>
                    <th>Processo</th><th>Empresa</th><th>Prefeitura</th>
                    <th>Data mov.</th><th>Descrição</th>
                </tr>
            </thead>
            <tbody>{html_movimentacoes}</tbody>
        </table>
    </section>

    <section>
        <h2>Últimas consultas realizadas</h2>
        <table>
            <thead>
                <tr>
                    <th>Processo</th><th>Empresa</th><th>Prefeitura</th>
                    <th>Resultado</th><th>Data/hora</th>
                </tr>
            </thead>
            <tbody>{html_consultas}</tbody>
        </table>
    </section>

    <section>
        <h2>Prefeituras sem robô configurado</h2>
        <table>
            <thead><tr><th>Órgão</th><th>Processos</th><th>URL</th></tr></thead>
            <tbody>{html_orgaos_sem_robo}</tbody>
        </table>
    </section>

    <div class="footer">SSA Monitor Processos · Dashboard Web</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# PÁGINA: /movimentacoes-hoje  (aceita ?data=YYYY-MM-DD)
# ─────────────────────────────────────────────
def _nav_datas(data_selecionada: date) -> str:
    """Gera a barra de navegação de datas (← ontem | data atual | amanhã →)."""
    hoje       = date.today()
    anterior   = data_selecionada - timedelta(days=1)
    proximo    = data_selecionada + timedelta(days=1)
    dias_semana_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    nome_dia = dias_semana_pt[data_selecionada.weekday()]

    label_data = (
        f"Hoje — {data_selecionada.strftime('%d/%m/%Y')}"
        if data_selecionada == hoje
        else f"{nome_dia}, {data_selecionada.strftime('%d/%m/%Y')}"
    )

    proximo_html = (
        f'<a href="/movimentacoes-hoje?data={proximo}">Amanhã &rarr;</a>'
        if proximo <= hoje
        else '<span style="color:#d1d5db;padding:8px 16px;border-radius:8px;border:1px solid #e5e7eb;">Amanhã →</span>'
    )

    return f"""
    <div class="nav-data">
        <a href="/movimentacoes-hoje?data={anterior}">&larr; Dia anterior</a>
        <span class="data-atual">📅 {label_data}</span>
        {proximo_html}
        <form method="get" action="/movimentacoes-hoje" style="display:inline-flex;align-items:center;gap:8px;">
            <input type="date" name="data" value="{data_selecionada}"
                   max="{hoje}" onchange="this.form.submit()">
        </form>
        {'<a href="/movimentacoes-hoje">↩ Ir para hoje</a>' if data_selecionada != hoje else ''}
    </div>"""


def _html_movimentacoes_expandidas(movs):
    """Gera o conteúdo HTML da linha expandida com as movimentações do dia."""
    if not movs:
        return '<p style="color:#6b7280;margin:0">Nenhuma movimentação registrada para este dia.</p>'
    linhas = ""
    for m in movs:
        dt  = escape(str(m.get("data_movimento") or "—"))
        hr  = escape(str(m.get("hora_captura") or "")[:5])
        desc = escape(str(m.get("descricao") or "").strip()[:300])
        # Só exibe linhas que parecem tramitações reais (têm data e texto)
        if not desc or len(desc) < 5:
            continue
        linhas += f"""
        <tr style="background:#f8fafc;">
            <td style="white-space:nowrap;color:#6b7280;font-size:12px;padding:6px 10px;">{dt}</td>
            <td style="color:#6b7280;font-size:12px;padding:6px 10px;">{hr}</td>
            <td style="font-size:13px;white-space:normal;max-width:600px;padding:6px 10px;">{desc}</td>
        </tr>"""
    if not linhas:
        return '<p style="color:#6b7280;margin:0">Detalhes não disponíveis para este dia.</p>'
    return f"""
    <table style="width:100%;border-collapse:collapse;margin-top:6px;">
        <thead>
            <tr>
                <th style="font-size:11px;color:#9ca3af;text-align:left;padding:4px 10px;white-space:nowrap;">Data mov.</th>
                <th style="font-size:11px;color:#9ca3af;text-align:left;padding:4px 10px;">Capturado às</th>
                <th style="font-size:11px;color:#9ca3af;text-align:left;padding:4px 10px;">Descrição</th>
            </tr>
        </thead>
        <tbody>{linhas}</tbody>
    </table>"""


def gerar_html_movimentacoes_hoje(data_str=None):
    hoje = date.today()
    try:
        data_sel = date.fromisoformat(data_str) if data_str else hoje
        if data_sel > hoje:
            data_sel = hoje
    except (ValueError, TypeError):
        data_sel = hoje

    data_param = str(data_sel) if data_sel != hoje else None

    processos     = buscar_detalhe_movimentacoes_hoje(data_param)
    mov_por_orgao = buscar_movimentacoes_hoje_por_orgao(data_param)
    total_dia     = buscar_total_movimentacoes_recentes(data_param)
    movs_agrupadas       = buscar_movimentacoes_do_dia_agrupadas(data_param)
    movs_historico       = buscar_ultimas_movimentacoes_todos_processos()

    # Cards de prefeitura — clicáveis para filtrar a tabela
    cards_orgaos = ""
    for item in mov_por_orgao:
        orgao_raw = str(item.get("orgao") or "")
        orgao     = escape(orgao_raw)
        tp = item.get("total_processos", 0)
        tm = item.get("total_movimentacoes", 0)
        cards_orgaos += f"""
        <div class="card alerta" style="min-width:160px;cursor:pointer;"
             onclick="filtrarPrefeitura('{orgao_raw}')"
             title="Filtrar por {orgao}">
            <h2>{tp}</h2>
            <p>{orgao}</p>
            <div class="hint">{tm} movimentaç{'ão' if tm == 1 else 'ões'} · clique para filtrar</div>
        </div>"""

    if not cards_orgaos:
        cards_orgaos = '<p style="color:#6b7280">Nenhuma movimentação detectada neste dia.</p>'

    # Linhas da tabela — clicáveis para expandir movimentações
    linhas = ""
    idx = 0
    for p in processos:
        pid    = p.get("processo_id", "")
        num    = escape(str(p.get("numero_processo") or ""))
        emp    = escape(str(p.get("empresa") or "—"))
        orgao_raw = str(p.get("orgao") or "")
        orgao  = escape(orgao_raw)
        status = _badge_status(str(p.get("status_atual") or ""))
        total  = p.get("total_movimentacoes_hoje", 0)
        dt_mov = escape(str(p.get("data_ultimo_movimento") or "—"))
        ult_c  = escape(str(p.get("ultima_consulta") or "—"))

        # Movimentações deste dia (pode ser vazio)
        movs_hoje_proc = movs_agrupadas.get(pid, [])
        # Histórico completo (últimas N movimentações do banco)
        movs_hist_proc = movs_historico.get(pid, [])

        if total > 0:
            indicador = f'<span class="badge verde">✔ {total} nova{"s" if total > 1 else ""}</span>'
            cor_linha  = "background:#fff8f0;"
            cor_borda  = "#f97316"
            titulo_det = f"Movimentacoes detectadas neste dia — processo {num}"
            conteudo_expandido = _html_movimentacoes_expandidas(movs_hoje_proc)
        elif movs_hist_proc:
            indicador = '<span class="badge cinza">— sem mov. hoje</span>'
            cor_linha  = ""
            cor_borda  = "#d1d5db"
            titulo_det = f"Ultimo historico registrado — processo {num}"
            conteudo_expandido = _html_movimentacoes_expandidas(movs_hist_proc)
        else:
            indicador = '<span class="badge cinza">— sem mov.</span>'
            cor_linha  = ""
            cor_borda  = "#d1d5db"
            titulo_det = f"Processo {num}"
            conteudo_expandido = '<p style="color:#6b7280;margin:0">Nenhuma movimentacao registrada no historico.</p>'

        link_detalhe = f"/processo/{pid}"

        linhas += f"""
        <tr data-prefeitura="{escape(orgao_raw)}" data-tem-mov="{1 if total > 0 else 0}"
            style="{cor_linha}"
            onclick="window.location='{link_detalhe}'"
            title="Ver detalhes e movimentacoes"
            class="linha-processo">
            <td>
                <a href="{link_detalhe}" style="color:inherit;text-decoration:none;font-weight:700;">
                    {num}
                </a>
            </td>
            <td style="max-width:160px">{emp}</td>
            <td>{orgao}</td>
            <td>{status}</td>
            <td>{indicador}</td>
            <td>{dt_mov}</td>
            <td style="color:#9ca3af;font-size:12px">{ult_c} <span style="float:right">›</span></td>
        </tr>"""

        idx += 1

    if not linhas:
        linhas = '<tr><td colspan="7" class="vazio">Nenhum processo encontrado.</td></tr>'

    titulo = (
        "Movimentações de Hoje"
        if data_sel == hoje
        else f"Movimentações de {data_sel.strftime('%d/%m/%Y')}"
    )

    js = """
    <script>
    let filtroAtivo = null;
    function filtrarPrefeitura(nome) {
        const rows = document.querySelectorAll('tr[data-prefeitura]');

        if (filtroAtivo === nome) {
            rows.forEach(r => r.style.display = '');
            filtroAtivo = null;
            document.getElementById('aviso-filtro').style.display = 'none';
            return;
        }

        filtroAtivo = nome;
        rows.forEach(r => {
            r.style.display = (r.dataset.prefeitura === nome) ? '' : 'none';
        });

        const av = document.getElementById('aviso-filtro');
        av.style.display = '';
        av.innerHTML = '🔍 Filtrando por: <strong>' + nome + '</strong> &nbsp;'
            + '<a href="#" onclick="filtrarPrefeitura(\'' + nome + '\');return false;"'
            + ' style="color:#2563eb;">limpar filtro ✕</a>';
    }
    </script>
    """

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>{escape(titulo)} · SSA Monitor</title>
    <style>{CSS_BASE}
    tr.linha-processo {{ cursor: pointer; }}
    tr.linha-processo:hover td {{ background:#f0f4ff !important; }}
    </style>
</head>
<body>
    <h1>{escape(titulo)}</h1>
    <div class="subtitulo">Todos os processos ativos · movimentações detectadas pelo robô neste dia</div>
    {_nav("/movimentacoes-hoje")}
    {_nav_datas(data_sel)}

    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:25px;">
        <div class="card alerta" style="min-width:160px;">
            <h2>{total_dia}</h2>
            <p>Processos com mov. neste dia</p>
        </div>
        {cards_orgaos}
    </div>

    <section>
        <h2>Situação de todos os processos</h2>
        <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">
            <span class="badge verde">✔ N novas</span> = movimentacoes detectadas neste dia &nbsp;|&nbsp;
            <span class="badge cinza">— sem mov. hoje</span> = sem novidade hoje, mas tem historico &nbsp;|&nbsp;
            <strong>Clique em qualquer linha</strong> para ver as movimentacoes
        </div>
        <div id="aviso-filtro" style="display:none;background:#dbeafe;color:#1e40af;
             padding:8px 14px;border-radius:8px;margin-bottom:10px;font-size:13px;"></div>
        <table>
            <thead>
                <tr>
                    <th>Processo</th>
                    <th>Empresa</th>
                    <th>Prefeitura</th>
                    <th>Status</th>
                    <th>Hoje</th>
                    <th>Último mov.</th>
                    <th>Última consulta</th>
                </tr>
            </thead>
            <tbody>{linhas}</tbody>
        </table>
    </section>

    <div class="footer">SSA Monitor Processos · Movimentações Hoje</div>
    {js}
</body>
</html>"""


# ─────────────────────────────────────────────
# PÁGINA: /processo/<id>  — detalhe completo
# ─────────────────────────────────────────────
def gerar_html_detalhe_processo(processo_id: int):
    processo  = buscar_processo_por_id_dashboard(processo_id)
    if not processo:
        return None

    movimentacoes = buscar_movimentacoes_do_processo(processo_id)
    historico     = buscar_historico_consultas_do_processo(processo_id)

    num    = escape(str(processo.get("numero_processo") or ""))
    emp    = escape(str(processo.get("empresa") or "—"))
    orgao  = escape(str(processo.get("orgao") or ""))
    mun    = escape(str(processo.get("municipio") or orgao))
    status = _badge_status(str(processo.get("status_atual") or ""))
    robo   = escape(str(processo.get("robo") or "—"))
    dt_mov = escape(str(processo.get("data_ultimo_movimento") or "—"))
    ult_c  = escape(str(processo.get("ultima_consulta") or "—"))
    url_o  = escape(str(processo.get("url_orgao") or ""))

    # Movimentações
    linhas_mov = ""
    for m in movimentacoes:
        dt   = escape(str(m.get("data_movimento") or "—"))
        dc   = escape(str(m.get("data_captura") or ""))
        hr   = escape(str(m.get("hora_captura") or "")[:5])
        desc = escape(str(m.get("descricao") or "").strip())
        if not desc or len(desc) < 5:
            continue
        linhas_mov += f"""
        <tr>
            <td style="white-space:nowrap;color:#6b7280;font-size:13px;">{dt}</td>
            <td style="white-space:nowrap;color:#9ca3af;font-size:12px;">{dc} {hr}</td>
            <td style="white-space:normal;font-size:14px;">{desc}</td>
        </tr>"""
    if not linhas_mov:
        linhas_mov = '<tr><td colspan="3" class="vazio">Nenhuma movimentação registrada.</td></tr>'

    # Histórico de consultas
    linhas_hist = ""
    for h in historico:
        sc  = str(h.get("status_consulta") or "")
        dc  = escape(str(h.get("data_consulta") or ""))
        msg = escape(str(h.get("mensagem") or "")[:120])
        if sc == "OK":
            badge = f'<span class="badge verde">{escape(sc)}</span>'
        elif "NAO_ENCONTRADO" in sc or "ERRO" in sc:
            badge = f'<span class="badge laranja">{escape(sc)}</span>'
        else:
            badge = f'<span class="badge cinza">{escape(sc)}</span>'
        linhas_hist += f"""
        <tr>
            <td>{badge}</td>
            <td style="color:#6b7280;font-size:13px;">{dc}</td>
            <td style="white-space:normal;font-size:13px;color:#374151;">{msg}</td>
        </tr>"""
    if not linhas_hist:
        linhas_hist = '<tr><td colspan="3" class="vazio">Nenhuma consulta registrada.</td></tr>'

    link_portal = (
        f'<a href="{url_o}" target="_blank" style="color:#2563eb;font-size:13px;">'
        f'Abrir no portal da prefeitura ›</a>'
        if url_o else ""
    )

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Processo {num} · SSA Monitor</title>
    <style>{CSS_BASE}</style>
</head>
<body>
    <h1>Processo {num}</h1>
    <div class="subtitulo">{emp} · {orgao}</div>
    {_nav("/movimentacoes-hoje")}
    <a href="javascript:history.back()" class="btn secundario" style="margin-bottom:20px;display:inline-block;">
        &larr; Voltar
    </a>

    <div class="cards" style="grid-template-columns:repeat(3,minmax(160px,1fr));margin-bottom:25px;">
        <div class="card">
            <h2 style="font-size:20px;">{num}</h2>
            <p>Numero do processo</p>
        </div>
        <div class="card">
            <h2 style="font-size:20px;">{mun}</h2>
            <p>Prefeitura / Municipio</p>
        </div>
        <div class="card sucesso">
            <h2 style="font-size:20px;">{status}</h2>
            <p>Status atual</p>
        </div>
    </div>

    <section style="margin-bottom:20px;">
        <table style="width:auto;font-size:14px;">
            <tr><td style="color:#6b7280;padding:4px 12px 4px 0;">Empresa</td>     <td><strong>{emp}</strong></td></tr>
            <tr><td style="color:#6b7280;padding:4px 12px 4px 0;">Robo</td>        <td>{robo}</td></tr>
            <tr><td style="color:#6b7280;padding:4px 12px 4px 0;">Ultimo mov.</td> <td>{dt_mov}</td></tr>
            <tr><td style="color:#6b7280;padding:4px 12px 4px 0;">Ultima consulta</td><td>{ult_c}</td></tr>
            {"<tr><td style='color:#6b7280;padding:4px 12px 4px 0;'>Portal</td><td>" + link_portal + "</td></tr>" if link_portal else ""}
        </table>
    </section>

    <section>
        <h2>Historico de movimentacoes <span style="font-size:14px;color:#6b7280;font-weight:normal;">({len(movimentacoes)} registros)</span></h2>
        <table>
            <thead>
                <tr>
                    <th style="white-space:nowrap;">Data mov.</th>
                    <th style="white-space:nowrap;">Capturado em</th>
                    <th>Descricao</th>
                </tr>
            </thead>
            <tbody>{linhas_mov}</tbody>
        </table>
    </section>

    <section>
        <h2>Historico de consultas do robo <span style="font-size:14px;color:#6b7280;font-weight:normal;">(ultimas {len(historico)})</span></h2>
        <table>
            <thead>
                <tr>
                    <th>Resultado</th>
                    <th>Data/hora</th>
                    <th>Mensagem</th>
                </tr>
            </thead>
            <tbody>{linhas_hist}</tbody>
        </table>
    </section>

    <div class="footer">SSA Monitor Processos · Detalhe do Processo</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────
class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suprime logs de acesso no terminal (produção)
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        rota = parsed.path

        try:
            qs = parse_qs(parsed.query)
            if rota == "/":
                html = gerar_html_dashboard()
            elif rota == "/movimentacoes-hoje":
                data_param = qs.get("data", [None])[0]
                html = gerar_html_movimentacoes_hoje(data_param)
            elif rota.startswith("/processo/"):
                # /processo/<id>
                partes = rota.rstrip("/").split("/")
                pid_str = partes[-1] if partes else ""
                if not pid_str.isdigit():
                    self.send_response(400)
                    self.end_headers()
                    return
                html = gerar_html_detalhe_processo(int(pid_str))
                if html is None:
                    self.send_response(404)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write("<h2>Processo nao encontrado.</h2>".encode("utf-8"))
                    return
            else:
                self.send_response(404)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h2>Pagina nao encontrada.</h2>".encode("utf-8"))
                return

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            erro = f"<h2>Erro interno</h2><pre>{escape(str(e))}</pre>"
            self.wfile.write(erro.encode("utf-8"))


def iniciar_dashboard():
    servidor = HTTPServer((HOST, PORTA), DashboardHandler)
    print("\n=== DASHBOARD SSA MONITOR PROCESSOS ===")
    print(f"Acesse: http://{HOST}:{PORTA}")
    print(f"Movimentações hoje: http://{HOST}:{PORTA}/movimentacoes-hoje")
    print("Pressione CTRL + C para encerrar.")
    servidor.serve_forever()


if __name__ == "__main__":
    iniciar_dashboard()
