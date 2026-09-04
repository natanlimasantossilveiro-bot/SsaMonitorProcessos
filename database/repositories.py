import re
from database.connection import criar_conexao
from utils.crypto_utils import criptografar, descriptografar

_PATTERN_HORARIO = re.compile(r'\d{2}/\d{2}/\d{4}\s*(\d{2}:\d{2}:\d{2})')
_PATTERN_ROTULOS = re.compile(r'\b(Usu[aá]rio|Origem|Destino):\s*')


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


def cadastrar_processo_manual(orgao_id, numero_processo, empresa, cnpj, municipio):
    """Cadastra um processo via formulário do dashboard (sem credenciais de acesso ao portal)."""
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO processos (orgao_id, empresa, cnpj, municipio, numero_processo, cliente)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (orgao_id, empresa, cnpj or None, municipio, numero_processo, empresa))

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
          AND (processos.status_atual IS NULL
               OR processos.status_atual NOT IN ('Encerrado', 'Finalizado', 'Indeferido', 'Deferido'))
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


def atualizar_objeto_processo(processo_id, objeto):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE processos SET objeto = %s WHERE id = %s AND objeto IS NULL
    """, (objeto, processo_id))

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
def _tipo_movimento(texto):
    """Classifica o tipo estrutural do movimento para evitar dedup entre tipos distintos."""
    t = texto or ''
    if 'Observação de Abertura' in t or 'Observacao de Abertura' in t:
        return 'abertura'
    if 'Origem:' in t or 'Destino:' in t:
        return 'tramite'
    return 'simples'


def movimentacao_ja_existe(processo_id, data, descricao):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    # Check 1: correspondência exata
    cursor.execute("""
        SELECT id
        FROM movimentacoes
        WHERE processo_id = %s
        AND data_movimento <=> %s
        AND descricao = %s
        LIMIT 1
    """, (processo_id, data, descricao))

    if cursor.fetchone():
        cursor.close()
        conexao.close()
        return True

    # Check 2: prefixo bruto de 60 chars (captura variantes com/sem rótulo numerado,
    # ex: "10 - Recebimento" vs versão sem numeração).
    prefixo = (descricao or "").strip()[:60]
    if len(prefixo) >= 30:
        cursor.execute("""
            SELECT id
            FROM movimentacoes
            WHERE processo_id = %s
            AND data_movimento <=> %s
            AND descricao LIKE %s
            LIMIT 1
        """, (processo_id, data, f"{prefixo}%"))
        if cursor.fetchone():
            cursor.close()
            conexao.close()
            return True

    # Check 3: mesmo evento com/sem rótulo "Usuário:" — o portal ora inclui o rótulo,
    # ora omite, fazendo o prefixo bruto divergir antes do nome. Normaliza removendo
    # rótulos variáveis e compara 80 chars. Restringe ao mesmo tipo estrutural
    # (simples/abertura/tramite) para não deduplicar um par Abertura+Trâmite legítimo
    # que o portal registra no mesmo segundo.
    horario = _PATTERN_HORARIO.search(descricao or '')
    if horario:
        hms = horario.group(1)
        tipo_novo = _tipo_movimento(descricao)
        desc_norm = _PATTERN_ROTULOS.sub('', descricao or '').strip()[:80]
        if len(desc_norm) >= 30:
            cursor.execute("""
                SELECT id, descricao
                FROM movimentacoes
                WHERE processo_id = %s
                AND data_movimento <=> %s
                AND descricao LIKE %s
            """, (processo_id, data, f'%{hms}%'))
            for row in cursor.fetchall():
                if _tipo_movimento(row['descricao']) != tipo_novo:
                    continue
                stored_norm = _PATTERN_ROTULOS.sub('', row['descricao'] or '').strip()[:80]
                if stored_norm == desc_norm:
                    cursor.close()
                    conexao.close()
                    return True

    cursor.close()
    conexao.close()
    return False


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