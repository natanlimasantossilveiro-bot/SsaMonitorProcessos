import os
import mysql.connector

from dotenv import load_dotenv


load_dotenv()


def criar_conexao():
    """
    Cria e retorna uma conexão com o banco de dados MySQL.
    """

    conexao = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )

    return conexao