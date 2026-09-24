from api.db import obter_conexao

# Queries de leitura dedicadas à API. Nunca reaproveitar funções de
# database/repositories.py que decriptam login_acesso/senha_acesso — a API
# de leitura consumida pelo Laravel não deve expor credenciais dos portais.


def listar_orgaos():
    conexao = obter_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, nome, tipo, url, chave_robo,
               possui_login, possui_captcha, ativo
        FROM orgaos
        ORDER BY nome
    """)

    dados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return dados


def listar_processos(orgao_id=None, status_atual=None, limite=50, offset=0):
    conexao = obter_conexao()
    cursor = conexao.cursor(dictionary=True)

    condicoes = []
    parametros = []

    if orgao_id is not None:
        condicoes.append("processos.orgao_id = %s")
        parametros.append(orgao_id)

    if status_atual is not None:
        condicoes.append("processos.status_atual = %s")
        parametros.append(status_atual)

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    parametros.extend([limite, offset])

    cursor.execute(f"""
        SELECT
            processos.id, processos.orgao_id, processos.numero_processo,
            processos.empresa, processos.cnpj, processos.municipio,
            processos.exercicio, processos.codigo,
            processos.status_processo, processos.status_atual,
            processos.data_ultimo_movimento, processos.ultima_movimentacao,
            processos.ultima_consulta, processos.ativo,
            orgaos.nome AS nome_orgao
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        {where}
        ORDER BY processos.id
        LIMIT %s OFFSET %s
    """, parametros)

    dados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return dados


def buscar_processo_por_id(processo_id):
    conexao = obter_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            processos.id, processos.orgao_id, processos.numero_processo,
            processos.empresa, processos.cnpj, processos.municipio,
            processos.exercicio, processos.codigo,
            processos.status_processo, processos.status_atual,
            processos.data_ultimo_movimento, processos.ultima_movimentacao,
            processos.ultima_consulta, processos.ativo,
            orgaos.nome AS nome_orgao
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        WHERE processos.id = %s
    """, (processo_id,))

    processo = cursor.fetchone()
    cursor.close()
    conexao.close()
    return processo


def listar_movimentacoes_do_processo(processo_id):
    conexao = obter_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, processo_id, data_movimento, descricao
        FROM movimentacoes
        WHERE processo_id = %s
        ORDER BY data_movimento DESC, id DESC
    """, (processo_id,))

    dados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return dados
