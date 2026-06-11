from database.connection import criar_conexao


def cadastrar_processo(orgao_id, numero_processo, cliente=None):
    """
    Cadastra um novo processo no banco de dados.
    """

    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        INSERT INTO processos (
            orgao_id,
            numero_processo,
            cliente
        )
        VALUES (%s, %s, %s)
    """

    valores = (
        orgao_id,
        numero_processo,
        cliente,
    )

    cursor.execute(query, valores)

    conexao.commit()

    processo_id = cursor.lastrowid

    cursor.close()
    conexao.close()

    return processo_id


def listar_processos_ativos():
    """
    Lista todos os processos ativos com os dados do órgão.
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
            orgaos.id AS orgao_id,
            orgaos.nome AS nome_orgao,
            orgaos.tipo AS tipo_orgao,
            orgaos.url AS url_orgao
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        WHERE processos.ativo = TRUE
        ORDER BY processos.id;
    """

    cursor.execute(query)

    processos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return processos


def buscar_processo_por_id(processo_id):
    """
    Busca um processo específico pelo ID.
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
            orgaos.id AS orgao_id,
            orgaos.nome AS nome_orgao,
            orgaos.tipo AS tipo_orgao,
            orgaos.url AS url_orgao
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        WHERE processos.id = %s;
    """

    cursor.execute(query, (processo_id,))

    processo = cursor.fetchone()

    cursor.close()
    conexao.close()

    return processo


def buscar_processos_por_orgao(orgao_id):

    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT *
        FROM processos
        WHERE orgao_id = %s
        AND ativo = TRUE;
    """

    cursor.execute(query, (orgao_id,))

    processos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return processos