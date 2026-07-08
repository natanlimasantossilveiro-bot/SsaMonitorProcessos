from datetime import datetime, timedelta

from database.connection import criar_conexao


def buscar_usuario_por_email(email):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios WHERE email = %s LIMIT 1;", (email,))
    usuario = cursor.fetchone()

    cursor.close()
    conexao.close()

    return usuario


def buscar_usuario_por_id(usuario_id):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios WHERE id = %s LIMIT 1;", (usuario_id,))
    usuario = cursor.fetchone()

    cursor.close()
    conexao.close()

    return usuario


def listar_usuarios():
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, nome, email, is_admin, ativo, precisa_trocar_senha,
               criado_em, ultimo_login
        FROM usuarios
        ORDER BY nome;
    """)
    usuarios = cursor.fetchall()

    cursor.close()
    conexao.close()

    return usuarios


def criar_usuario(nome, email, senha_hash, is_admin=False):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO usuarios (nome, email, senha_hash, is_admin, ativo, precisa_trocar_senha)
        VALUES (%s, %s, %s, %s, TRUE, TRUE);
    """, (nome, email, senha_hash, is_admin))

    conexao.commit()
    usuario_id = cursor.lastrowid

    cursor.close()
    conexao.close()

    return usuario_id


def atualizar_senha(usuario_id, senha_hash, precisa_trocar_senha=False):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET senha_hash = %s, precisa_trocar_senha = %s
        WHERE id = %s;
    """, (senha_hash, precisa_trocar_senha, usuario_id))

    conexao.commit()
    cursor.close()
    conexao.close()


def atualizar_status(usuario_id, ativo):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("UPDATE usuarios SET ativo = %s WHERE id = %s;", (ativo, usuario_id))

    conexao.commit()
    cursor.close()
    conexao.close()


def excluir_usuario(usuario_id):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("DELETE FROM sessoes WHERE usuario_id = %s;", (usuario_id,))
    cursor.execute("UPDATE log_acessos SET usuario_id = NULL WHERE usuario_id = %s;", (usuario_id,))
    cursor.execute("DELETE FROM usuarios WHERE id = %s;", (usuario_id,))

    conexao.commit()
    cursor.close()
    conexao.close()


def atualizar_ultimo_login(usuario_id):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s;", (usuario_id,))

    conexao.commit()
    cursor.close()
    conexao.close()


def criar_sessao(token, usuario_id, ip, duracao_horas=12):
    expira_em = datetime.now() + timedelta(hours=duracao_horas)

    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO sessoes (token, usuario_id, expira_em, ip)
        VALUES (%s, %s, %s, %s);
    """, (token, usuario_id, expira_em, ip))

    conexao.commit()
    cursor.close()
    conexao.close()


def buscar_sessao_valida(token):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT sessoes.token, sessoes.usuario_id, sessoes.expira_em,
               usuarios.nome, usuarios.email, usuarios.is_admin,
               usuarios.ativo, usuarios.precisa_trocar_senha
        FROM sessoes
        INNER JOIN usuarios ON usuarios.id = sessoes.usuario_id
        WHERE sessoes.token = %s
        AND sessoes.expira_em > NOW()
        LIMIT 1;
    """, (token,))
    sessao = cursor.fetchone()

    cursor.close()
    conexao.close()

    if sessao and not sessao.get("ativo"):
        return None

    return sessao


def invalidar_sessao(token):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("DELETE FROM sessoes WHERE token = %s;", (token,))

    conexao.commit()
    cursor.close()
    conexao.close()


def invalidar_sessoes_do_usuario(usuario_id):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("DELETE FROM sessoes WHERE usuario_id = %s;", (usuario_id,))

    conexao.commit()
    cursor.close()
    conexao.close()


def registrar_tentativa_acesso(email_tentado, sucesso, ip, rota, usuario_id=None):
    conexao = criar_conexao()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO log_acessos (usuario_id, email_tentado, sucesso, ip, rota)
        VALUES (%s, %s, %s, %s, %s);
    """, (usuario_id, email_tentado, sucesso, ip, rota))

    conexao.commit()
    cursor.close()
    conexao.close()


def contar_falhas_recentes_por_email(email_tentado, minutos=15):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM log_acessos
        WHERE sucesso = FALSE
        AND criado_em >= (NOW() - INTERVAL %s MINUTE)
        AND email_tentado = %s;
    """, (minutos, email_tentado))
    resultado = cursor.fetchone()

    cursor.close()
    conexao.close()

    return resultado["total"] if resultado else 0


def contar_falhas_recentes_por_ip(ip, minutos=15):
    conexao = criar_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM log_acessos
        WHERE sucesso = FALSE
        AND criado_em >= (NOW() - INTERVAL %s MINUTE)
        AND ip = %s;
    """, (minutos, ip))
    resultado = cursor.fetchone()

    cursor.close()
    conexao.close()

    return resultado["total"] if resultado else 0
