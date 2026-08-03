"""
Script avulso chamado pelo dashboard para executar o monitoramento manualmente.
Atualiza o arquivo .monitor_status.json durante a execução, incluindo progresso.
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
            status.update({"running": True, "iniciado_em": agora, "source": "manual",
                           "concluidos": 0, "total": 0, "orgao_atual": ""})
        else:
            status.update({"running": False, "finalizado_em": agora,
                           "concluidos": 0, "total": 0, "orgao_atual": ""})
        with open(_STATUS_FILE, "w") as f:
            json.dump(status, f)
    except Exception:
        pass


async def _tarefa_progresso():
    import services.monitoramento_service as svc
    while True:
        try:
            status = {}
            if os.path.exists(_STATUS_FILE):
                with open(_STATUS_FILE) as f:
                    status = json.load(f)
            p = svc._progresso
            status.update({
                "concluidos": p["concluidos"],
                "total":      p["total"],
                "orgao_atual": p["orgao_atual"],
            })
            with open(_STATUS_FILE, "w") as f:
                json.dump(status, f)
        except Exception:
            pass
        await asyncio.sleep(2)


async def main():
    from services.monitoramento_service import monitorar_processos_ativos
    _set_status(True)
    tarefa = asyncio.create_task(_tarefa_progresso())
    try:
        await monitorar_processos_ativos()
    finally:
        tarefa.cancel()
        _set_status(False)


if __name__ == "__main__":
    asyncio.run(main())
