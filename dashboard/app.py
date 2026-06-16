import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

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
)

from dashboard.dashboard_html import (
    gerar_linhas_tabela,
)


HOST = "localhost"
PORTA = 8000


def buscar_dados_dashboard():
    return {
        "total_processos": buscar_total_processos(),
        "processos_monitorados": buscar_processos_monitorados(),
        "processos_sem_robo": buscar_processos_sem_robo(),
        "total_orgaos": buscar_total_orgaos(),
        "processos_por_status": buscar_processos_por_status(),
        "ranking_orgaos": buscar_ranking_orgaos(),
        "ultimas_movimentacoes": buscar_ultimas_movimentacoes(),
        "orgaos_sem_robo": buscar_orgaos_sem_robo(),
        "ultimas_consultas": buscar_ultimas_consultas(),
    }


def gerar_html():
    dados = buscar_dados_dashboard()

    html_status = gerar_linhas_tabela(
        dados["processos_por_status"],
        ["status", "total"]
    )

    html_ranking_orgaos = gerar_linhas_tabela(
        dados["ranking_orgaos"],
        ["orgao", "total_processos"]
    )

    html_movimentacoes = gerar_linhas_tabela(
        dados["ultimas_movimentacoes"],
        [
            "numero_processo",
            "empresa",
            "orgao",
            "data_movimento",
            "descricao",
        ]
    )

    html_orgaos_sem_robo = gerar_linhas_tabela(
        dados["orgaos_sem_robo"],
        ["nome", "total_processos", "url"]
    )

    html_consultas = gerar_linhas_tabela(
        dados["ultimas_consultas"],
        [
            "numero_processo",
            "empresa",
            "orgao",
            "status_consulta",
            "data_consulta",
        ]
    )

    return f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>SSA Monitor Processos</title>
        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                margin: 0;
                padding: 24px;
                color: #111827;
            }}

            h1 {{
                margin-bottom: 5px;
                font-size: 32px;
            }}

            h2 {{
                margin-top: 0;
            }}

            .subtitulo {{
                color: #6b7280;
                margin-bottom: 25px;
            }}

            .cards {{
                display: grid;
                grid-template-columns: repeat(4, minmax(180px, 1fr));
                gap: 18px;
                margin-bottom: 25px;
            }}

            .card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                border-left: 5px solid #2563eb;
            }}

            .card.alerta {{
                border-left-color: #f97316;
            }}

            .card.sucesso {{
                border-left-color: #16a34a;
            }}

            .card.neutro {{
                border-left-color: #6b7280;
            }}

            .card h2 {{
                margin: 0;
                font-size: 34px;
                color: #0f172a;
            }}

            .card p {{
                margin: 6px 0 0;
                color: #6b7280;
                font-size: 14px;
            }}

            .grid-duplo {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 25px;
            }}

            section {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 25px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                overflow-x: auto;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}

            th, td {{
                border-bottom: 1px solid #e5e7eb;
                padding: 10px;
                text-align: left;
                font-size: 14px;
                vertical-align: top;
            }}

            th {{
                background: #f8fafc;
                color: #374151;
            }}

            tr:hover td {{
                background: #f9fafb;
            }}

            .vazio {{
                text-align: center;
                color: #6b7280;
                padding: 20px;
            }}

            .footer {{
                text-align: center;
                color: #777;
                margin-top: 30px;
                font-size: 13px;
            }}

            @media (max-width: 1000px) {{
                .cards {{
                    grid-template-columns: repeat(2, 1fr);
                }}

                .grid-duplo {{
                    grid-template-columns: 1fr;
                }}
            }}

            @media (max-width: 600px) {{
                .cards {{
                    grid-template-columns: 1fr;
                }}

                body {{
                    padding: 12px;
                }}
            }}
        </style>
    </head>
    <body>
        <h1>SSA Monitor Processos</h1>
        <div class="subtitulo">Dashboard gerencial de acompanhamento dos processos monitorados</div>

        <div class="cards">
            <div class="card">
                <h2>{dados["total_processos"]}</h2>
                <p>Total de processos</p>
            </div>

            <div class="card sucesso">
                <h2>{dados["processos_monitorados"]}</h2>
                <p>Processos monitorados</p>
            </div>

            <div class="card alerta">
                <h2>{dados["processos_sem_robo"]}</h2>
                <p>Sem robô configurado</p>
            </div>

            <div class="card neutro">
                <h2>{dados["total_orgaos"]}</h2>
                <p>Total de órgãos/links</p>
            </div>
        </div>

        <div class="grid-duplo">
            <section>
                <h2>Processos por status atual</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_status}
                    </tbody>
                </table>
            </section>

            <section>
                <h2>Ranking de órgãos por processos</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Órgão</th>
                            <th>Total de processos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_ranking_orgaos}
                    </tbody>
                </table>
            </section>
        </div>

        <section>
            <h2>Últimas movimentações</h2>
            <table>
                <thead>
                    <tr>
                        <th>Processo</th>
                        <th>Empresa</th>
                        <th>Órgão</th>
                        <th>Data</th>
                        <th>Movimentação</th>
                    </tr>
                </thead>
                <tbody>
                    {html_movimentacoes}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Últimas consultas</h2>
            <table>
                <thead>
                    <tr>
                        <th>Processo</th>
                        <th>Empresa</th>
                        <th>Órgão</th>
                        <th>Status consulta</th>
                        <th>Data consulta</th>
                    </tr>
                </thead>
                <tbody>
                    {html_consultas}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Órgãos/links sem robô configurado</h2>
            <table>
                <thead>
                    <tr>
                        <th>Órgão</th>
                        <th>Total de processos</th>
                        <th>URL</th>
                    </tr>
                </thead>
                <tbody>
                    {html_orgaos_sem_robo}
                </tbody>
            </table>
        </section>

        <div class="footer">
            SSA Monitor Processos - Dashboard Web
        </div>
    </body>
    </html>
    """


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        rota = urlparse(self.path).path

        if rota != "/":
            self.send_response(404)
            self.end_headers()
            self.wfile.write("Página não encontrada.".encode("utf-8"))
            return

        html = gerar_html()

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def iniciar_dashboard():
    servidor = HTTPServer((HOST, PORTA), DashboardHandler)

    print("\n=== DASHBOARD SSA MONITOR PROCESSOS ===")
    print(f"Acesse: http://{HOST}:{PORTA}")
    print("Pressione CTRL + C para encerrar.")

    servidor.serve_forever()


if __name__ == "__main__":
    iniciar_dashboard()