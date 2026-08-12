"""
Grava login/senha do RI Digital (criptografados) nos processos com robo='ridigital'.
Execute uma vez, na raiz do projeto:
    python scripts/atualizar_credenciais_ridigital.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.crypto_utils import criptografar
from database.connection import criar_conexao

login_raw = input("Login RI Digital (e-mail): ").strip()
senha_raw = input("Senha RI Digital: ").strip()

if not login_raw or not senha_raw:
    print("Credenciais não podem ser vazias.")
    sys.exit(1)

login_enc = criptografar(login_raw)
senha_enc = criptografar(senha_raw)

conexao = criar_conexao()
cursor = conexao.cursor()

cursor.execute("""
    UPDATE processos
    SET login_acesso = %s, senha_acesso = %s
    WHERE robo = 'ridigital'
      AND (login_acesso IS NULL OR senha_acesso IS NULL)
""", (login_enc, senha_enc))

conexao.commit()
print(f"Credenciais atualizadas para {cursor.rowcount} processo(s).")

cursor.close()
conexao.close()