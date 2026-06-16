from database.connection import criar_conexao


def buscar_orgao_por_url(url):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orgaos WHERE url = %s LIMIT 1;",
        (url,)
    )

    orgao = cursor.fetchone()

    cursor.close()
    conexao.close()

    return orgao


def cadastrar_orgao(nome, tipo, url, chave_robo=None):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        INSERT INTO orgaos (
            nome,
            tipo,
            url,
            chave_robo,
            possui_login,
            possui_captcha
        )
        VALUES (%s, %s, %s, %s, FALSE, FALSE);
    """

    cursor.execute(
        query,
        (nome, tipo, url, chave_robo)
    )

    conexao.commit()
    orgao_id = cursor.lastrowid

    cursor.close()
    conexao.close()

    return orgao_id


def obter_ou_criar_orgao(nome, tipo, url, chave_robo=None):
    orgao = buscar_orgao_por_url(url)

    if orgao:
        return orgao["id"]

    return cadastrar_orgao(
        nome=nome,
        tipo=tipo,
        url=url,
        chave_robo=chave_robo,
    )


def listar_orgaos():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT
            id,
            nome,
            tipo,
            url,
            chave_robo,
            possui_login,
            possui_captcha,
            ativo
        FROM orgaos
        ORDER BY nome, url;
    """

    cursor.execute(query)
    orgaos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return orgaos


def buscar_processo_por_orgao_e_numero(orgao_id, numero_processo):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT *
        FROM processos
        WHERE orgao_id = %s
        AND numero_processo = %s
        LIMIT 1;
    """

    cursor.execute(
        query,
        (orgao_id, numero_processo)
    )

    processo = cursor.fetchone()

    cursor.close()
    conexao.close()

    return processo


def cadastrar_ou_atualizar_processo_planilha(dados):
    processo_existente = buscar_processo_por_orgao_e_numero(
        dados["orgao_id"],
        dados["numero_processo"]
    )

    conexao = criar_conexao()
    cursor = conexao.cursor()

    if processo_existente:
        query = """
            UPDATE processos
            SET
                empresa = %s,
                cnpj = %s,
                municipio = %s,
                exercicio = %s,
                codigo = %s,
                acesso = %s,
                login_acesso = %s,
                senha_acesso = %s,
                cliente = %s,
                ativo = TRUE
            WHERE id = %s;
        """

        cursor.execute(
            query,
            (
                dados["empresa"],
                dados["cnpj"],
                dados["municipio"],
                dados["exercicio"],
                dados["codigo"],
                dados["acesso"],
                dados["login"],
                dados["senha"],
                dados["empresa"],
                processo_existente["id"],
            )
        )

        processo_id = processo_existente["id"]

    else:
        query = """
            INSERT INTO processos (
                orgao_id,
                empresa,
                cnpj,
                municipio,
                exercicio,
                numero_processo,
                codigo,
                acesso,
                login_acesso,
                senha_acesso,
                cliente
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """

        cursor.execute(
            query,
            (
                dados["orgao_id"],
                dados["empresa"],
                dados["cnpj"],
                dados["municipio"],
                dados["exercicio"],
                dados["numero_processo"],
                dados["codigo"],
                dados["acesso"],
                dados["login"],
                dados["senha"],
                dados["empresa"],
            )
        )

        processo_id = cursor.lastrowid

    conexao.commit()

    cursor.close()
    conexao.close()

    return processo_id


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


def listar_processos_ativos_com_orgao():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    query = """
        SELECT
            processos.*,
            orgaos.nome AS nome_orgao,
            orgaos.tipo AS tipo_orgao,
            orgaos.url AS url_orgao,
            orgaos.chave_robo AS chave_robo,
            orgaos.possui_login AS orgao_possui_login,
            orgaos.possui_captcha AS orgao_possui_captcha
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


def atualizar_caminho_solicitacao_captcha(processo_id, caminho_solicitacao):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        UPDATE processos
        SET caminho_solicitacao_captcha = %s
        WHERE id = %s;
    """

    cursor.execute(
        query,
        (
            caminho_solicitacao,
            processo_id,
        )
    )

    conexao.commit()
    cursor.close()
    conexao.close()


def limpar_caminho_solicitacao_captcha(processo_id):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    query = """
        UPDATE processos
        SET caminho_solicitacao_captcha = NULL
        WHERE id = %s;
    """

    cursor.execute(query, (processo_id,))

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


def obter_colunas_tabela(nome_tabela):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(f"DESCRIBE {nome_tabela};")
    colunas = cursor.fetchall()

    cursor.close()
    conexao.close()

    return [coluna["Field"] for coluna in colunas]


def registrar_historico_consulta(
    processo_id,
    status,
    mensagem=None
):
    colunas = obter_colunas_tabela("historico_consultas")

    dados = {}

    if "processo_id" in colunas:
        dados["processo_id"] = processo_id

    if "status_consulta" in colunas:
        dados["status_consulta"] = status

    if "status" in colunas:
        dados["status"] = status

    if "resultado" in colunas:
        dados["resultado"] = status

    if "mensagem" in colunas:
        dados["mensagem"] = mensagem

    if "observacao" in colunas:
        dados["observacao"] = mensagem

    if "observacoes" in colunas:
        dados["observacoes"] = mensagem

    campos_data_possiveis = [
        "data_consulta",
        "consultado_em",
        "created_at",
        "criado_em",
    ]

    campo_data = None

    for campo in campos_data_possiveis:
        if campo in colunas:
            campo_data = campo
            break

    campos = list(dados.keys())
    valores = list(dados.values())

    placeholders = ["%s"] * len(valores)

    if campo_data:
        campos.append(campo_data)
        placeholders.append("NOW()")

    query = f"""
        INSERT INTO historico_consultas (
            {", ".join(campos)}
        )
        VALUES (
            {", ".join(placeholders)}
        );
    """

    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute(query, tuple(valores))

    conexao.commit()
    cursor.close()
    conexao.close()

    return True