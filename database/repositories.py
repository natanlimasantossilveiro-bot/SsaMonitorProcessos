import re
from database.connection import criar_conexao
from utils.crypto_utils import criptografar, descriptografar

_PATTERN_HORARIO = re.compile(r'\d{2}/\d{2}/\d{4}\s*(\d{2}:\d{2}:\d{2})')


# =====================================================
# ✅ ORGÃOS
# =====================================================
def buscar_orgao_por_url(url):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orgaos WHERE url = %s LIMIT 1;", (url,))
    orgao = cursor.fetchone()

    cursor.close()
    conexao.close()
    return orgao


def cadastrar_orgao(nome, tipo, url, chave_robo=None):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO orgaos (
            nome, tipo, url, chave_robo,
            possui_login, possui_captcha
        )
        VALUES (%s, %s, %s, %s, FALSE, FALSE)
    """, (nome, tipo, url, chave_robo))

    conexao.commit()
    orgao_id = cursor.lastrowid

    cursor.close()
    conexao.close()
    return orgao_id


def obter_ou_criar_orgao(nome, tipo, url, chave_robo=None):
    orgao = buscar_orgao_por_url(url)
    if orgao:
        return orgao["id"]
    return cadastrar_orgao(nome, tipo, url, chave_robo)


def listar_orgaos():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, nome, tipo, url,
               chave_robo, possui_login,
               possui_captcha, ativo
        FROM orgaos
        ORDER BY nome
    """)

    dados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return dados


# =====================================================
# ✅ PROCESSOS
# =====================================================
def buscar_processo_por_orgao_e_numero(orgao_id, numero_processo):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM processos
        WHERE orgao_id = %s
        AND numero_processo = %s
        LIMIT 1
    """, (orgao_id, numero_processo))

    processo = cursor.fetchone()

    cursor.close()
    conexao.close()
    return processo


def buscar_processo_por_id(processo_id):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT * FROM processos WHERE id = %s", (processo_id,))
    processo = cursor.fetchone()

    cursor.close()
    conexao.close()
    return processo


def buscar_processos_por_orgao(orgao_id):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM processos
        WHERE orgao_id = %s
        AND ativo = TRUE
    """, (orgao_id,))

    dados = cursor.fetchall()

    cursor.close()
    conexao.close()
    return dados


def cadastrar_ou_atualizar_processo_planilha(dados):
    processo_existente = buscar_processo_por_orgao_e_numero(
        dados["orgao_id"], dados["numero_processo"]
    )

    # login_acesso/senha_acesso são credenciais dos portais dos órgãos —
    # nunca gravar em texto puro no banco.
    login_acesso_criptografado = criptografar(dados.get("login_acesso") or dados.get("Login"))
    senha_acesso_criptografada = criptografar(dados.get("senha_acesso") or dados.get("Senha"))

    conexao = criar_conexao()
    cursor = conexao.cursor()

    if processo_existente:
        cursor.execute("""
            UPDATE processos SET
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
            WHERE id = %s
        """, (
            dados["empresa"],
            dados["cnpj"],
            dados["municipio"],
            dados["exercicio"],
            dados["codigo"],
            dados["acesso"],
            login_acesso_criptografado,
            senha_acesso_criptografada,
            dados["empresa"],
            processo_existente["id"]
        ))

        processo_id = processo_existente["id"]

    else:
        cursor.execute("""
            INSERT INTO processos (
                orgao_id, empresa, cnpj, municipio,
                exercicio, numero_processo, codigo,
                acesso, login_acesso, senha_acesso, cliente
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            dados["orgao_id"],
            dados["empresa"],
            dados["cnpj"],
            dados["municipio"],
            dados["exercicio"],
            dados["numero_processo"],
            dados["codigo"],
            dados["acesso"],
            login_acesso_criptografado,
            senha_acesso_criptografada,
            dados["empresa"]
        ))

        processo_id = cursor.lastrowid

    conexao.commit()
    cursor.close()
    conexao.close()

    return processo_id


# =====================================================
# ✅ LISTAGEM
# =====================================================
def listar_processos_ativos_com_orgao():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            processos.id,
            processos.numero_processo,
            processos.empresa,
            processos.cnpj,
            processos.municipio,
            processos.exercicio,
            processos.codigo,
            processos.acesso,
            processos.login_acesso,
            processos.senha_acesso,
            processos.cliente,
            processos.ativo,
            processos.robo,

            orgaos.nome AS nome_orgao,
            orgaos.tipo AS tipo_orgao,
            orgaos.url AS url_orgao,
            orgaos.chave_robo,
            orgaos.possui_login,
            orgaos.possui_captcha
        FROM processos
        INNER JOIN orgaos ON processos.orgao_id = orgaos.id
        WHERE processos.ativo = TRUE
        ORDER BY processos.id
    """)

    dados = cursor.fetchall()

    cursor.close()
    conexao.close()

    # Decripta aqui — único ponto de onde os robôs recebem essas credenciais.
    for processo in dados:
        processo["login_acesso"] = descriptografar(processo.get("login_acesso"))
        processo["senha_acesso"] = descriptografar(processo.get("senha_acesso"))

    return dados


# =====================================================
# ✅ ATUALIZAÇÃO
# =====================================================

def atualizar_dados_processo(
    processo_id,
    status_processo,
    data_ultimo_movimento,
    ultima_movimentacao,
    monitorado
):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    # COALESCE: só atualiza status/data/movimentação se o novo valor não for NULL.
    # Evita que consultas com erro (PROCESSO_NAO_ENCONTRADO etc.) apaguem
    # um status válido que já estava gravado de uma consulta anterior.
    cursor.execute("""
        UPDATE processos SET
            status_processo      = COALESCE(%s, status_processo),
            status_atual         = COALESCE(%s, status_atual),
            data_ultimo_movimento = COALESCE(%s, data_ultimo_movimento),
            ultima_movimentacao  = COALESCE(%s, ultima_movimentacao),
            monitorado           = %s,
            ultima_consulta      = NOW()
        WHERE id = %s
    """, (
        status_processo,
        status_processo,
        data_ultimo_movimento,
        ultima_movimentacao,
        monitorado,
        processo_id
    ))

    conexao.commit()
    cursor.close()
    conexao.close()


def atualizar_caminho_solicitacao_captcha(processo_id, caminho):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE processos
        SET caminho_solicitacao_captcha = %s
        WHERE id = %s
    """, (caminho, processo_id))

    conexao.commit()
    cursor.close()
    conexao.close()


def limpar_caminho_solicitacao_captcha(processo_id):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE processos
        SET caminho_solicitacao_captcha = NULL
        WHERE id = %s
    """, (processo_id,))

    conexao.commit()
    cursor.close()
    conexao.close()


# =====================================================
# ✅ MOVIMENTAÇÕES
# =====================================================
def movimentacao_ja_existe(processo_id, data, descricao):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id
        FROM movimentacoes
        WHERE processo_id = %s
        AND data_movimento <=> %s
        AND descricao = %s
        LIMIT 1
    """, (processo_id, data, descricao))

    resultado = cursor.fetchone()

    cursor.close()
    conexao.close()
    return resultado is not None


def registrar_movimentacao(processo_id, data, descricao):
    if movimentacao_ja_existe(processo_id, data, descricao):
        return False

    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO movimentacoes (
            processo_id,
            data_movimento,
            descricao
        )
        VALUES (%s, %s, %s)
    """, (processo_id, data, descricao))

    conexao.commit()
    cursor.close()
    conexao.close()

    return True


# =====================================================
# ✅ HISTÓRICO
# =====================================================
def registrar_historico_consulta(processo_id, status, mensagem=None):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO historico_consultas (
            processo_id,
            status_consulta,
            mensagem,
            data_consulta
        )
        VALUES (%s, %s, %s, NOW())
    """, (processo_id, status, mensagem))

    conexao.commit()
    cursor.close()
    conexao.close()
    return True


# =====================================================
# ✅ ALTERAÇÕES
# =====================================================
def registrar_alteracoes(processo_id, alteracoes):
    if not alteracoes:
        return 0

    conexao = criar_conexao()
    cursor = conexao.cursor()

    total = 0

    for alt in alteracoes:
        cursor.execute("""
            INSERT INTO alteracoes_detectadas (
                processo_id,
                tipo,
                valor_anterior,
                valor_novo
            )
            VALUES (%s, %s, %s, %s)
        """, (
            processo_id,
            alt.get("tipo"),
            alt.get("antes"),
            alt.get("depois")
        ))
        total += 1

    conexao.commit()
    cursor.close()
    conexao.close()

    return total