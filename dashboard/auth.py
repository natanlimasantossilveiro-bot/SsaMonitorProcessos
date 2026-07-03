import hmac
import hashlib
import os
import secrets

import bcrypt

from dashboard import auth_repository

NOME_COOKIE_SESSAO = "session"

# Limite por e-mail é baixo (protege cada conta individualmente).
# Limite por IP é bem mais alto: como o dashboard só é acessível pelo IP
# público do escritório (allowlist no nginx), todo mundo compartilha o
# mesmo IP — um limite baixo aqui bloquearia o escritório inteiro por causa
# de uma pessoa errando a senha algumas vezes.
LIMITE_TENTATIVAS_LOGIN_EMAIL = 5
LIMITE_TENTATIVAS_LOGIN_IP = 30
JANELA_RATE_LIMIT_MINUTOS = 15

SESSION_SECRET = os.getenv("SESSION_SECRET", "")


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def gerar_token_sessao() -> str:
    return secrets.token_hex(32)


def gerar_token_csrf(token_sessao: str) -> str:
    return hmac.new(
        SESSION_SECRET.encode("utf-8"),
        token_sessao.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def csrf_valido(token_sessao: str, token_csrf: str) -> bool:
    esperado = gerar_token_csrf(token_sessao)
    return hmac.compare_digest(esperado, token_csrf or "")


def extrair_cookie(header_cookie: str, nome: str):
    if not header_cookie:
        return None

    for parte in header_cookie.split(";"):
        parte = parte.strip()
        if parte.startswith(f"{nome}="):
            return parte[len(nome) + 1:]

    return None


def montar_cookie_sessao(token: str, seguro: bool = True) -> str:
    flags = "HttpOnly; SameSite=Strict; Path=/"
    if seguro:
        flags += "; Secure"

    return f"{NOME_COOKIE_SESSAO}={token}; Max-Age=43200; {flags}"


def montar_cookie_expirado() -> str:
    return f"{NOME_COOKIE_SESSAO}=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/"


def limite_tentativas_excedido(email: str, ip: str) -> bool:
    falhas_email = auth_repository.contar_falhas_recentes_por_email(
        email_tentado=email,
        minutos=JANELA_RATE_LIMIT_MINUTOS,
    )
    if falhas_email >= LIMITE_TENTATIVAS_LOGIN_EMAIL:
        return True

    falhas_ip = auth_repository.contar_falhas_recentes_por_ip(
        ip=ip,
        minutos=JANELA_RATE_LIMIT_MINUTOS,
    )
    return falhas_ip >= LIMITE_TENTATIVAS_LOGIN_IP


def autenticar_usuario(email: str, senha: str, ip: str):
    """
    Retorna (usuario, erro). Em caso de sucesso, erro é None.
    Toda tentativa (sucesso ou falha) é registrada em log_acessos.
    """

    if limite_tentativas_excedido(email, ip):
        return None, "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."

    usuario = auth_repository.buscar_usuario_por_email(email)

    senha_confere = bool(usuario) and verificar_senha(senha, usuario["senha_hash"])
    sucesso = bool(usuario) and usuario.get("ativo") and senha_confere

    auth_repository.registrar_tentativa_acesso(
        email_tentado=email,
        sucesso=sucesso,
        ip=ip,
        rota="/login",
        usuario_id=usuario["id"] if usuario else None,
    )

    if not usuario or not senha_confere:
        return None, "E-mail ou senha inválidos."

    if not usuario.get("ativo"):
        return None, "Usuário desativado. Fale com o administrador."

    return usuario, None
