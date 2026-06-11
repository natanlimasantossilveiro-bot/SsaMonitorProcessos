from database.connection import criar_conexao


def listar_orgaos():
    """
    Lista todos os órgãos cadastrados no banco de dados.
    """

    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orgaos")

    orgaos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return orgaos


def listar_processos_ativos():
    """
    Lista todos os processos ativos junto com os dados do órgão.
    """

    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT 
            processos.id,
            processos.numero_processo,
            processos.cliente,
            processos.status_atual,
            processos.data_ultimo_movimento,
            processos.ultima_movimentacao,
            processos.ultima_consulta,
            orgaos.nome AS nome_orgao,
            orgaos.tipo AS tipo_orgao,
            orgaos.url AS url_orgao
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        WHERE processos.ativo = TRUE;
    """

    cursor.execute(query)

    processos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return processos