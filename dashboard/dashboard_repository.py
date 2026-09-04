from database.connection import criar_conexao


def executar_query(query):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(query)
    resultado = cursor.fetchall()

    cursor.close()
    conexao.close()

    return resultado


def executar_query_unica(query):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(query)
    resultado = cursor.fetchone()

    cursor.close()
    conexao.close()

    return resultado


def buscar_ultima_execucao():
    """Retorna a data/hora da última consulta registrada no histórico."""
    resultado = executar_query_unica(
        "SELECT MAX(data_consulta) AS ultima FROM historico_consultas"
    )
    return resultado["ultima"] if resultado else None


def buscar_total_processos():
    resultado = executar_query_unica(
        "SELECT COUNT(*) AS total FROM processos WHERE ativo = TRUE;"
    )
    return resultado["total"]


def buscar_processos_monitorados():
    resultado = executar_query_unica("""
        SELECT COUNT(*) AS total
        FROM processos
        WHERE ativo = TRUE
          AND (status_atual IS NULL
               OR status_atual NOT IN ('Encerrado', 'Finalizado', 'Indeferido', 'Deferido'));
    """)
    return resultado["total"]


def buscar_processos_sem_robo():
    resultado = executar_query_unica("""
        SELECT COUNT(*) AS total
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE o.chave_robo IS NULL;
    """)
    return resultado["total"]


def buscar_total_orgaos():
    resultado = executar_query_unica(
        "SELECT COUNT(*) AS total FROM orgaos;"
    )
    return resultado["total"]


def buscar_processos_encerrados():
    resultado = executar_query_unica("""
        SELECT COUNT(*) AS total
        FROM processos
        WHERE ativo = TRUE
          AND status_atual IN ('Encerrado', 'Finalizado', 'Indeferido', 'Deferido');
    """)
    return resultado["total"]


def buscar_processos_por_status():
    return executar_query("""
        SELECT
            COALESCE(status_atual, 'Sem status') AS status,
            COUNT(*) AS total
        FROM processos
        GROUP BY COALESCE(status_atual, 'Sem status')
        ORDER BY total DESC;
    """)


def buscar_ranking_orgaos():
    return executar_query("""
        SELECT
            o.nome AS orgao,
            COUNT(p.id) AS total_processos
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        GROUP BY o.id, o.nome
        ORDER BY total_processos DESC;
    """)


def buscar_ultimas_movimentacoes():
    return executar_query("""
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


def buscar_orgaos_sem_robo():
    return executar_query("""
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


def buscar_ultimas_consultas():
    return executar_query("""
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


def buscar_total_movimentacoes_recentes(data=None):
    """
    Total de processos que tiveram movimentação na data indicada (padrão: hoje).
    Usa data_movimento (data real da movimentação na prefeitura), não capturado_em,
    para evitar contar movimentos históricos detectados pela primeira vez hoje.
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    if data:
        cursor.execute(
            "SELECT COUNT(DISTINCT m.processo_id) AS total FROM movimentacoes m WHERE m.data_movimento = %s",
            (data,),
        )
    else:
        cursor.execute(
            "SELECT COUNT(DISTINCT m.processo_id) AS total FROM movimentacoes m WHERE m.data_movimento = CURDATE()"
        )
    resultado = cursor.fetchone()
    cursor.close()
    conexao.close()
    return resultado["total"]


def buscar_movimentacoes_hoje_por_orgao(data=None):
    """Movimentações por prefeitura agrupadas pela data real do movimento."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    filtro = "m.data_movimento = %s" if data else "m.data_movimento = CURDATE()"
    sql = f"""
        SELECT
            o.nome AS orgao,
            COUNT(DISTINCT m.processo_id) AS total_processos,
            COUNT(*) AS total_movimentacoes
        FROM movimentacoes m
        INNER JOIN processos p ON m.processo_id = p.id
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE {filtro}
        GROUP BY o.id, o.nome
        ORDER BY total_processos DESC
    """
    cursor.execute(sql, (data,) if data else ())
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado


def buscar_detalhe_movimentacoes_hoje(data=None):
    """
    Todos os processos ativos com indicação de movimentação na data escolhida.
    Filtra por data_movimento (data real na prefeitura), não por capturado_em.
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    filtro = "m.data_movimento = %s" if data else "m.data_movimento = CURDATE()"
    sql = f"""
        SELECT
            p.id AS processo_id,
            p.numero_processo,
            p.empresa,
            o.nome AS orgao,
            p.status_atual,
            p.ultima_consulta,
            p.data_ultimo_movimento,
            COUNT(m.id) AS total_movimentacoes_hoje,
            MAX(m.data_movimento) AS ultima_data_hoje,
            MAX(m.descricao) AS ultima_descricao_hoje
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        LEFT JOIN movimentacoes m
            ON m.processo_id = p.id
            AND {filtro}
        WHERE p.ativo = TRUE
        GROUP BY p.id, p.numero_processo, p.empresa, o.nome,
                 p.status_atual, p.ultima_consulta, p.data_ultimo_movimento
        ORDER BY total_movimentacoes_hoje DESC, o.nome, p.numero_processo
    """
    params = (data,) if data else ()
    cursor.execute(sql, params)
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado


def buscar_ultimas_movimentacoes_todos_processos(limite_por_processo: int = 15):
    """
    Retorna as últimas N movimentações de todos os processos ativos, agrupadas
    por processo_id. Permite exibir histórico mesmo quando não há mov. hoje.
    Resultado: dict {processo_id: [{"data_movimento": ..., "descricao": ...}, ...]}
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.processo_id, m.data_movimento, m.descricao,
               TIME(m.capturado_em) AS hora_captura
        FROM movimentacoes m
        INNER JOIN processos p ON m.processo_id = p.id
        WHERE p.ativo = TRUE
          AND m.descricao IS NOT NULL
          AND LENGTH(TRIM(m.descricao)) > 5
        ORDER BY m.processo_id, m.id DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conexao.close()

    agrupado = {}
    contagem = {}
    for row in rows:
        pid = row["processo_id"]
        if pid not in agrupado:
            agrupado[pid] = []
            contagem[pid] = 0
        if contagem[pid] < limite_por_processo:
            agrupado[pid].append(row)
            contagem[pid] += 1
    return agrupado


def buscar_movimentacoes_do_dia_agrupadas(data=None):
    """
    Movimentações do dia agrupadas por processo_id.
    Usa data_movimento (data real da prefeitura).
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    filtro = "m.data_movimento = %s" if data else "m.data_movimento = CURDATE()"
    sql = f"""
        SELECT
            m.processo_id,
            m.data_movimento,
            m.descricao,
            TIME(m.capturado_em) AS hora_captura
        FROM movimentacoes m
        WHERE {filtro}
        ORDER BY m.processo_id, m.id ASC
    """
    cursor.execute(sql, (data,) if data else ())
    rows = cursor.fetchall()
    cursor.close()
    conexao.close()

    agrupado = {}
    for row in rows:
        pid = row["processo_id"]
        if pid not in agrupado:
            agrupado[pid] = []
        agrupado[pid].append(row)
    return agrupado


def buscar_historico_7_dias():
    """
    Últimos 7 dias com contagem de processos que tiveram movimentação.
    Usa data_movimento (quando o movimento aconteceu na prefeitura).
    """
    return executar_query("""
        SELECT
            m.data_movimento AS dia,
            COUNT(DISTINCT m.processo_id) AS total_processos,
            COUNT(*) AS total_movimentacoes
        FROM movimentacoes m
        WHERE m.data_movimento >= CURDATE() - INTERVAL 6 DAY
          AND m.data_movimento IS NOT NULL
        GROUP BY m.data_movimento
        ORDER BY dia ASC
    """)


# ─────────────────────────────────────────────
# Página de detalhe de processo
# ─────────────────────────────────────────────

def buscar_movimentacoes_do_mes(ano: int, mes: int):
    """
    Retorna todas as movimentações de um mês, agrupadas por dia e processo.
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            m.data_movimento AS dia,
            p.id            AS processo_id,
            p.numero_processo,
            p.empresa,
            o.nome          AS orgao,
            COUNT(*)        AS total
        FROM movimentacoes m
        JOIN processos p ON p.id = m.processo_id
        LEFT JOIN orgaos o ON o.id = p.orgao_id
        WHERE YEAR(m.data_movimento) = %s
          AND MONTH(m.data_movimento) = %s
          AND m.data_movimento IS NOT NULL
        GROUP BY m.data_movimento, p.id, p.numero_processo, p.empresa, o.nome
        ORDER BY m.data_movimento, p.id
    """, (ano, mes))
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado


def buscar_processo_por_id_dashboard(processo_id: int):
    """Retorna os dados completos de um processo com nome do órgão."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            p.id, p.numero_processo, p.empresa, p.cnpj,
            p.municipio, p.exercicio, p.codigo, p.objeto,
            p.acesso, p.cliente,
            p.status_atual, p.status_processo,
            p.data_ultimo_movimento, p.ultima_movimentacao,
            p.ultima_consulta, p.monitorado, p.robo,
            p.criado_em, p.ativo,
            o.nome AS orgao, o.url AS url_orgao
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE p.id = %s
    """, (processo_id,))
    resultado = cursor.fetchone()
    cursor.close()
    conexao.close()
    return resultado


def buscar_movimentacoes_do_processo(processo_id: int):
    """Retorna todas as movimentações de um processo, ordenadas da mais recente."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            m.id,
            m.data_movimento,
            m.descricao,
            DATE(m.capturado_em)  AS data_captura,
            TIME(m.capturado_em)  AS hora_captura
        FROM movimentacoes m
        WHERE m.processo_id = %s
          AND m.descricao IS NOT NULL
          AND LENGTH(TRIM(m.descricao)) > 5
        ORDER BY m.data_movimento DESC, m.capturado_em DESC, m.id DESC
    """, (processo_id,))
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado


# ─────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────

def buscar_filtros_relatorio():
    """Listas de prefeituras, empresas e status para os dropdowns do relatório."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT o.nome FROM orgaos o
        INNER JOIN processos p ON p.orgao_id = o.id
        WHERE p.ativo = TRUE ORDER BY o.nome
    """)
    orgaos = [r['nome'] for r in cursor.fetchall()]
    cursor.execute("""
        SELECT DISTINCT empresa FROM processos
        WHERE ativo = TRUE AND empresa IS NOT NULL AND empresa != ''
        ORDER BY empresa
    """)
    empresas = [r['empresa'] for r in cursor.fetchall()]
    cursor.execute("""
        SELECT DISTINCT status_atual FROM processos
        WHERE ativo = TRUE AND status_atual IS NOT NULL AND status_atual != ''
        ORDER BY status_atual
    """)
    statuses = [r['status_atual'] for r in cursor.fetchall()]
    cursor.close()
    conexao.close()
    return orgaos, empresas, statuses


def buscar_dados_relatorio(data_inicio, data_fim, orgao=None, empresa=None, status=None):
    """
    Processos ativos com movimentações no período informado.
    Retorna (dict agrupado por prefeitura, list de todos os processos).
    """
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    where = ["p.ativo = TRUE"]
    params = []
    if orgao:
        where.append("o.nome = %s")
        params.append(orgao)
    if empresa:
        where.append("p.empresa = %s")
        params.append(empresa)
    if status:
        where.append("p.status_atual = %s")
        params.append(status)

    cursor.execute(f"""
        SELECT p.id, p.numero_processo, p.empresa, p.status_atual,
               p.objeto, p.data_ultimo_movimento, o.nome AS orgao
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE {' AND '.join(where)}
        ORDER BY o.nome, p.empresa, p.numero_processo
    """, params)
    processos = cursor.fetchall()

    if processos:
        pids = [p['id'] for p in processos]
        fmt = ','.join(['%s'] * len(pids))
        cursor.execute(f"""
            SELECT m.processo_id, m.data_movimento, m.descricao,
                   DATE(m.capturado_em) AS data_captura
            FROM movimentacoes m
            WHERE m.processo_id IN ({fmt})
              AND m.data_movimento BETWEEN %s AND %s
              AND m.descricao IS NOT NULL
              AND LENGTH(TRIM(m.descricao)) > 5
            ORDER BY m.processo_id, m.data_movimento DESC, m.id DESC
        """, pids + [data_inicio, data_fim])
        movs = cursor.fetchall()
    else:
        movs = []

    cursor.close()
    conexao.close()

    movs_por_proc = {}
    for m in movs:
        movs_por_proc.setdefault(m['processo_id'], []).append(m)

    for p in processos:
        p['movimentacoes'] = movs_por_proc.get(p['id'], [])

    por_orgao = {}
    for p in processos:
        por_orgao.setdefault(p['orgao'], []).append(p)

    return por_orgao, processos


def buscar_todos_processos(orgao=None, empresa=None, status=None):
    """Lista completa de processos ativos com último resultado de consulta."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    where = ["p.ativo = TRUE"]
    params = []
    if orgao:
        where.append("o.nome = %s")
        params.append(orgao)
    if empresa:
        where.append("p.empresa = %s")
        params.append(empresa)
    if status:
        where.append("p.status_atual = %s")
        params.append(status)

    cursor.execute(f"""
        SELECT
            p.id,
            p.numero_processo,
            p.empresa,
            p.cliente,
            p.status_atual,
            p.ultima_consulta,
            p.data_ultimo_movimento,
            o.nome AS orgao,
            (
                SELECT h.status_consulta
                FROM historico_consultas h
                WHERE h.processo_id = p.id
                ORDER BY h.id DESC
                LIMIT 1
            ) AS ultimo_resultado
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE {' AND '.join(where)}
        ORDER BY o.nome, p.empresa, p.numero_processo
    """, params)
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado


def buscar_filtros_processos():
    """Listas de prefeituras, empresas e status para filtros da página Processos."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT o.nome FROM orgaos o
        INNER JOIN processos p ON p.orgao_id = o.id
        WHERE p.ativo = TRUE ORDER BY o.nome
    """)
    orgaos = [r['nome'] for r in cursor.fetchall()]
    cursor.execute("""
        SELECT DISTINCT empresa FROM processos
        WHERE ativo = TRUE AND empresa IS NOT NULL AND empresa != ''
        ORDER BY empresa
    """)
    empresas = [r['empresa'] for r in cursor.fetchall()]
    cursor.execute("""
        SELECT DISTINCT status_atual FROM processos
        WHERE ativo = TRUE AND status_atual IS NOT NULL AND status_atual != ''
        ORDER BY status_atual
    """)
    statuses = [r['status_atual'] for r in cursor.fetchall()]
    cursor.close()
    conexao.close()
    return orgaos, empresas, statuses


def buscar_historico_consultas_do_processo(processo_id: int, limite: int = 20):
    """Retorna as últimas N consultas registradas para um processo."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT status_consulta, mensagem, data_consulta
        FROM historico_consultas
        WHERE processo_id = %s
        ORDER BY id DESC
        LIMIT %s
    """, (processo_id, limite))
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado