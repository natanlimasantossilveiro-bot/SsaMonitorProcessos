import os
import threading
import time

from dotenv import load_dotenv
from mysql.connector import pooling
from mysql.connector.errors import PoolError

load_dotenv()

_pool = None
_pool_lock = threading.Lock()


def _criar_pool():
    global _pool
    if _pool is not None:
        return _pool

    # FastAPI roda cada request síncrona em uma thread do threadpool — sem o
    # lock, requests concorrentes na primeira chamada disparam N pools em
    # paralelo (cada um abrindo pool_size conexões de uma vez), estourando o
    # max_connections do MySQL.
    with _pool_lock:
        if _pool is not None:
            return _pool

        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        database = os.getenv("DB_NAME")

        if not all([host, user, password, database]):
            raise Exception("❌ Variáveis de ambiente do banco não carregadas.")

        tamanho = int(os.getenv("API_DB_POOL_SIZE", "10"))

        _pool = pooling.MySQLConnectionPool(
            pool_name="ssa_api_pool",
            pool_size=tamanho,
            host=host,
            user=user,
            password=password,
            database=database,
        )
        return _pool


_MAX_TENTATIVAS = 5
_ESPERA_ENTRE_TENTATIVAS = 0.1  # segundos


def obter_conexao():
    """
    Retorna uma conexão do pool da API (database/connection.py::criar_conexao
    continua intocado — os robôs seguem abrindo uma conexão nova por query).

    conexao.close() devolve a conexão ao pool em vez de encerrá-la, então o
    resto do código (cursor.close()/conexao.close()) não muda.

    Em rajadas que esgotam o pool momentaneamente, tenta de novo por até
    ~0.5s (as queries daqui são SELECTs simples, a conexão libera rápido)
    antes de propagar o PoolError.
    """
    pool = _criar_pool()
    ultimo_erro = None

    for _ in range(_MAX_TENTATIVAS):
        try:
            return pool.get_connection()
        except PoolError as e:
            ultimo_erro = e
            time.sleep(_ESPERA_ENTRE_TENTATIVAS)

    raise ultimo_erro
