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


def buscar_total_processos():
    resultado = executar_query_unica(
        "SELECT COUNT(*) AS total FROM processos;"
    )
    return resultado["total"]


def buscar_processos_monitorados():
    resultado = executar_query_unica("""
        SELECT COUNT(*) AS total
        FROM processos
        WHERE status_atual IS NOT NULL
        AND status_atual <> '';
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


def buscar_total_movimentacoes_recentes():
    resultado = executar_query_unica("""
        SELECT COUNT(DISTINCT m.processo_id) AS total
        FROM movimentacoes m
        WHERE DATE(m.capturado_em) = CURDATE();
    """)
    return resultado["total"]


def buscar_movimentacoes_hoje_por_orgao():
    """Agrupa movimentações de hoje por prefeitura — para o mini-gráfico do card."""
    return executar_query("""
        SELECT
            o.nome AS orgao,
            COUNT(DISTINCT m.processo_id) AS total_processos,
            COUNT(*) AS total_movimentacoes
        FROM movimentacoes m
        INNER JOIN processos p ON m.processo_id = p.id
        INNER JOIN orgaos o ON p.orgao_id = o.id
        WHERE DATE(m.capturado_em) = CURDATE()
        GROUP BY o.id, o.nome
        ORDER BY total_processos DESC;
    """)


def buscar_detalhe_movimentacoes_hoje():
    """Retorna todos os processos ativos com indicação se tiveram movimento hoje."""
    return executar_query("""
        SELECT
            p.id AS processo_id,
            p.numero_processo,
            p.empresa,
            o.nome AS orgao,
            p.status_atual,
            p.ultima_consulta,
            p.data_ultimo_movimento,
            COUNT(m.id) AS total_movimentacoes_hoje,
            MAX(m.capturado_em) AS ultima_captura_hoje,
            MAX(m.descricao) AS ultima_descricao_hoje
        FROM processos p
        INNER JOIN orgaos o ON p.orgao_id = o.id
        LEFT JOIN movimentacoes m
            ON m.processo_id = p.id
            AND DATE(m.capturado_em) = CURDATE()
        WHERE p.ativo = TRUE
        GROUP BY p.id, p.numero_processo, p.empresa, o.nome,
                 p.status_atual, p.ultima_consulta, p.data_ultimo_movimento
        ORDER BY total_movimentacoes_hoje DESC, o.nome, p.numero_processo;
    """)


def buscar_movimentacoes_de_processo_hoje(processo_id):
    """Retorna todas as movimentações de um processo específico capturadas hoje."""
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            m.data_movimento,
            m.descricao,
            m.capturado_em
        FROM movimentacoes m
        WHERE m.processo_id = %s
          AND DATE(m.capturado_em) = CURDATE()
        ORDER BY m.id ASC
    """, (processo_id,))
    resultado = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultado