"""
Script avulso chamado pelo dashboard para executar o monitoramento manualmente.
Atualiza o arquivo .monitor_status.json durante a execução.
"""
import asyncio
import json
import os
import sys
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

_STATUS_FILE = os.path.join(_BASE_DIR, ".monitor_status.json")


def _set_status(running: bool):
    try:
        status = {}
        if os.path.exists(_STATUS_FILE):
            with open(_STATUS_FILE) as f:
                status = json.load(f)
        agora = datetime.now().isoformat()
        if running:
            status.update({"running": True, "iniciado_em": agora, "source": "manual"})
        else:
            status.update({"running": False, "finalizado_em": agora})
        with open(_STATUS_FILE, "w") as f:
            json.dump(status, f)
    except Exception:
        pass


async def main():
    from services.monitoramento_service import monitorar_processos_ativos
    _set_status(True)
    try:
        await monitorar_processos_ativos()
    finally:
        _set_status(False)


if __name__ == "__main__":
    asyncio.run(main())
