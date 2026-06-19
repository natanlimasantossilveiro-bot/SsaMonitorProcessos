import os
import mysql.connector

from dotenv import load_dotenv


load_dotenv()


def criar_conexao():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if not all([host, user, password, database]):
        raise Exception("❌ Variáveis de ambiente do banco não carregadas.")

    conexao = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
    )

    return conexao