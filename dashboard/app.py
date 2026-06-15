import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import criar_conexao


HOST = "localhost"
PORTA = 8000


def buscar_dados_dashboard():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM processos;")
    total_processos = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT 
            COALESCE(status_atual, 'Sem status') AS status,
            COUNT(*) AS total
        FROM processos
        GROUP BY COALESCE(status_atual, 'Sem status')
        ORDER BY total DESC;
    """)
    processos_por_status = cursor.fetchall()

    cursor.execute("""
        SELECT
            p.numero_processo,
            p.empresa,
            o.nome AS orgao,
            m.data_movimento,
            m.descricao
        FROM movimentacoes m
        INNER JOIN processos p ON m.processo_id = p.id
        INNER JOIN orgaos o ON p.orgao_id = o.id
        ORDER BY m.data_movimento DESC, m.id DESC
        LIMIT 10;
    """)
    ultimas_movimentacoes = cursor.fetchall()

    cursor.execute("""
        SELECT
            o.nome,
            o.url,
            COUNT(p.id) AS total_processos
        FROM orgaos o
        INNER JOIN processos p ON p.orgao_id = o.id
        WHERE o.chave_robo IS NULL
        GROUP BY o.id, o.nome, o.url
        ORDER BY total_processos DESC;
    """)
    orgaos_sem_robo = cursor.fetchall()

    cursor.execute("""
        SELECT
            p.numero_processo,
            p.empresa,
            o.nome AS orgao,
            h.status_consulta,
            h.data_consulta
        FROM historico_consultas h
        INNER JOIN processos p ON h.processo_id = p.id
        INNER JOIN orgaos o ON p.orgao_id = o.id
        ORDER BY h.id DESC
        LIMIT 10;
    """)
    ultimas_consultas = cursor.fetchall()

    cursor.close()
    conexao.close()

    return {
        "total_processos": total_processos,
        "processos_por_status": processos_por_status,
        "ultimas_movimentacoes": ultimas_movimentacoes,
        "orgaos_sem_robo": orgaos_sem_robo,
        "ultimas_consultas": ultimas_consultas,
    }


def gerar_html():
    dados = buscar_dados_dashboard()

    html_status = ""
    for item in dados["processos_por_status"]:
        html_status += f"""
            <tr>
                <td>{item["status"]}</td>
                <td>{item["total"]}</td>
            </tr>
        """

    html_movimentacoes = ""
    for item in dados["ultimas_movimentacoes"]:
        html_movimentacoes += f"""
            <tr>
                <td>{item["numero_processo"]}</td>
                <td>{item["empresa"]}</td>
                <td>{item["orgao"]}</td>
                <td>{item["data_movimento"]}</td>
                <td>{item["descricao"]}</td>
            </tr>
        """

    html_orgaos_sem_robo = ""
    for item in dados["orgaos_sem_robo"]:
        html_orgaos_sem_robo += f"""
            <tr>
                <td>{item["nome"]}</td>
                <td>{item["total_processos"]}</td>
                <td>{item["url"]}</td>
            </tr>
        """

    html_consultas = ""
    for item in dados["ultimas_consultas"]:
        html_consultas += f"""
            <tr>
                <td>{item["numero_processo"]}</td>
                <td>{item["empresa"]}</td>
                <td>{item["orgao"]}</td>
                <td>{item["status_consulta"]}</td>
                <td>{item["data_consulta"]}</td>
            </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>SSA Monitor Processos</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                margin: 0;
                padding: 20px;
                color: #222;
            }}

            h1 {{
                margin-bottom: 5px;
            }}

            .subtitulo {{
                color: #666;
                margin-bottom: 25px;
            }}

            .cards {{
                display: flex;
                gap: 20px;
                margin-bottom: 25px;
                flex-wrap: wrap;
            }}

            .card {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                min-width: 220px;
            }}

            .card h2 {{
                margin: 0;
                font-size: 32px;
                color: #0f172a;
            }}

            .card p {{
                margin: 5px 0 0;
                color: #666;
            }}

            section {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 25px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
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
            }}

            th {{
                background: #f8fafc;
            }}

            .footer {{
                text-align: center;
                color: #777;
                margin-top: 30px;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <h1>SSA Monitor Processos</h1>
        <div class="subtitulo">Dashboard inicial de acompanhamento dos processos monitorados</div>

        <div class="cards">
            <div class="card">
                <h2>{dados["total_processos"]}</h2>
                <p>Total de processos cadastrados</p>
            </div>
        </div>

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

        <div class="footer">
            SSA Monitor Processos - primeira versão do dashboard
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