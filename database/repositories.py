from database.connection import criar_conexao


def cadastrar_processo(orgao_id, numero_processo, cliente=None):
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

    cursor.execute(query, (orgao_id, numero_processo, cliente))
    conexao.commit()

    processo_id = cursor.lastrowid

    cursor.close()
    conexao.close()

    return processo_id


def listar_processos_ativos():
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


def atualizar_dados_processo(
    processo_id,
    status_atual,
    data_ultimo_movimento,
    ultima_movimentacao
):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        UPDATE processos
        SET
            status_atual = %s,
            data_ultimo_movimento = STR_TO_DATE(%s, '%d/%m/%Y'),
            ultima_movimentacao = %s,
            ultima_consulta = NOW()
        WHERE id = %s;
    """

    cursor.execute(
        query,
        (
            status_atual,
            data_ultimo_movimento,
            ultima_movimentacao,
            processo_id,
        )
    )

    conexao.commit()
    cursor.close()
    conexao.close()


def movimentacao_ja_existe(
    processo_id,
    data_movimento,
    descricao
):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT id
        FROM movimentacoes
        WHERE processo_id = %s
        AND data_movimento = STR_TO_DATE(%s, '%d/%m/%Y')
        AND descricao = %s
        LIMIT 1;
    """

    cursor.execute(
        query,
        (
            processo_id,
            data_movimento,
            descricao,
        )
    )

    movimentacao = cursor.fetchone()

    cursor.close()
    conexao.close()

    return movimentacao is not None


def registrar_movimentacao(
    processo_id,
    data_movimento,
    descricao
):
    if movimentacao_ja_existe(
        processo_id,
        data_movimento,
        descricao
    ):
        return False

    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        INSERT INTO movimentacoes (
            processo_id,
            data_movimento,
            descricao
        )
        VALUES (
            %s,
            STR_TO_DATE(%s, '%d/%m/%Y'),
            %s
        );
    """

    cursor.execute(
        query,
        (
            processo_id,
            data_movimento,
            descricao,
        )
    )

    conexao.commit()
    cursor.close()
    conexao.close()

    return True