import os

from cryptography.fernet import Fernet, InvalidToken


def _obter_fernet():
    chave = os.getenv("ENCRYPTION_KEY")

    if not chave:
        raise Exception(
            "❌ ENCRYPTION_KEY não configurada no .env. "
            "Gere uma com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    return Fernet(chave.encode("utf-8"))


def criptografar(texto):
    if texto is None or texto == "":
        return texto

    return _obter_fernet().encrypt(str(texto).encode("utf-8")).decode("utf-8")


def descriptografar(texto):
    if texto is None or texto == "":
        return texto

    try:
        return _obter_fernet().decrypt(texto.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Valor ainda não criptografado (ex.: antes da migração) — devolve como está.
        return texto


def esta_criptografado(texto):
    if texto is None or texto == "":
        return True

    try:
        _obter_fernet().decrypt(texto.encode("utf-8"))
        return True
    except InvalidToken:
        return False
