import os
import sys
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
    buscar_movimentacoes_de_processo_hoje,
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
def gerar_html_dashboard():
    total_processos      = buscar_total_processos()
    processos_monitorados = buscar_processos_monitorados()
    total_orgaos         = buscar_total_orgaos()
    novas_movimentacoes  = buscar_total_movimentacoes_recentes()
    processos_por_status = buscar_processos_por_status()
    ranking_orgaos       = buscar_ranking_orgaos()
    ultimas_movimentacoes = buscar_ultimas_movimentacoes()
    orgaos_sem_robo      = buscar_orgaos_sem_robo()
    ultimas_consultas    = buscar_ultimas_consultas()
    mov_por_orgao        = buscar_movimentacoes_hoje_por_orgao()

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
# PÁGINA: /movimentacoes-hoje
# ─────────────────────────────────────────────
def gerar_html_movimentacoes_hoje():
    processos = buscar_detalhe_movimentacoes_hoje()
    mov_por_orgao = buscar_movimentacoes_hoje_por_orgao()
    total_hoje = buscar_total_movimentacoes_recentes()

    # Cards de resumo por prefeitura
    cards_orgaos = ""
    for item in mov_por_orgao:
        orgao = escape(str(item.get("orgao") or ""))
        tp = item.get("total_processos", 0)
        tm = item.get("total_movimentacoes", 0)
        cards_orgaos += f"""
        <div class="card alerta" style="min-width:160px;">
            <h2>{tp}</h2>
            <p>{orgao}</p>
            <div class="hint">{tm} movimentaç{'ão' if tm == 1 else 'ões'}</div>
        </div>"""

    if not cards_orgaos:
        cards_orgaos = '<p style="color:#6b7280">Nenhuma movimentação detectada hoje.</p>'

    # Tabela principal com todos os processos
    linhas = ""
    for p in processos:
        pid    = p.get("processo_id", "")
        num    = escape(str(p.get("numero_processo") or ""))
        emp    = escape(str(p.get("empresa") or "—"))
        orgao  = escape(str(p.get("orgao") or ""))
        status = _badge_status(str(p.get("status_atual") or ""))
        total  = p.get("total_movimentacoes_hoje", 0)
        dt_mov = escape(str(p.get("data_ultimo_movimento") or "—"))
        ult_c  = escape(str(p.get("ultima_consulta") or "—"))

        if total > 0:
            indicador = f'<span class="badge verde">✔ {total} nova{"s" if total > 1 else ""}</span>'
            # Busca descrição da última capturada hoje
            desc = escape(str(p.get("ultima_descricao_hoje") or "")[:80])
            linha_extra = f'<div style="font-size:12px;color:#374151;margin-top:4px;white-space:normal;">{desc}</div>'
        else:
            indicador   = '<span class="badge cinza">— sem mov.</span>'
            linha_extra = ""

        linhas += f"""<tr>
            <td><strong>{num}</strong></td>
            <td style="max-width:160px">{emp}</td>
            <td>{orgao}</td>
            <td>{status}</td>
            <td>{indicador}{linha_extra}</td>
            <td>{dt_mov}</td>
            <td style="color:#9ca3af;font-size:12px">{ult_c}</td>
        </tr>"""

    if not linhas:
        linhas = '<tr><td colspan="7" class="vazio">Nenhum processo encontrado.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="60">
    <title>Movimentações Hoje · SSA Monitor</title>
    <style>{CSS_BASE}</style>
</head>
<body>
    <h1>Movimentações de Hoje</h1>
    <div class="subtitulo">Todos os processos ativos · indica se houve nova movimentação detectada hoje</div>
    {_nav("/movimentacoes-hoje")}

    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:25px;">
        <div class="card alerta" style="min-width:160px;">
            <h2>{total_hoje}</h2>
            <p>Processos com mov. hoje</p>
        </div>
        {cards_orgaos}
    </div>

    <section>
        <h2>Situação de todos os processos</h2>
        <div style="font-size:13px;color:#6b7280;margin-bottom:10px;">
            <span class="badge verde">✔ N novas</span> = movimentações detectadas hoje &nbsp;|&nbsp;
            <span class="badge cinza">— sem mov.</span> = sem novidade hoje
        </div>
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
            if rota == "/":
                html = gerar_html_dashboard()
            elif rota == "/movimentacoes-hoje":
                html = gerar_html_movimentacoes_hoje()
            else:
                self.send_response(404)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>P\xc3\xa1gina n\xc3\xa3o encontrada.</h2>")
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
