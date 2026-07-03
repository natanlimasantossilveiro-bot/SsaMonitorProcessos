"""
Migração única: criptografa login_acesso/senha_acesso que hoje estão em texto
puro na tabela `processos`. Rodar UMA VEZ, depois de configurar ENCRYPTION_KEY
no .env e antes/depois de atualizar o código do repositories.py.

Uso:
    python -m scripts.migrar_criptografia_senhas
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import criar_conexao
from utils.crypto_utils import criptografar, esta_criptografado


def migrar():
    conexao = criar_conexao()
    cursor_leitura = conexao.cursor(dictionary=True)

    cursor_leitura.execute("SELECT id, login_acesso, senha_acesso FROM processos;")
    processos = cursor_leitura.fetchall()
    cursor_leitura.close()

    total_migrados = 0
    total_ja_criptografados = 0

    cursor_escrita = conexao.cursor()

    for processo in processos:
        login_ja_ok = esta_criptografado(processo.get("login_acesso"))
        senha_ja_ok = esta_criptografado(processo.get("senha_acesso"))

        if login_ja_ok and senha_ja_ok:
            total_ja_criptografados += 1
            continue

        novo_login = processo["login_acesso"] if login_ja_ok else criptografar(processo.get("login_acesso"))
        nova_senha = processo["senha_acesso"] if senha_ja_ok else criptografar(processo.get("senha_acesso"))

        cursor_escrita.execute(
            "UPDATE processos SET login_acesso = %s, senha_acesso = %s WHERE id = %s;",
            (novo_login, nova_senha, processo["id"]),
        )
        total_migrados += 1

    conexao.commit()
    cursor_escrita.close()
    conexao.close()

    print(f"Processos migrados agora: {total_migrados}")
    print(f"Processos já criptografados (ignorados): {total_ja_criptografados}")


if __name__ == "__main__":
    migrar()
