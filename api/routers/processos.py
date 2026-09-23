from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api import repository
from api.auth import verificar_token
from api.schemas import MovimentacaoOut, ProcessoOut

router = APIRouter(prefix="/processos", tags=["processos"], dependencies=[Depends(verificar_token)])


@router.get("", response_model=List[ProcessoOut])
def listar_processos(
    orgao_id: Optional[int] = None,
    status_atual: Optional[str] = None,
    limite: int = Query(default=50, le=200, gt=0),
    offset: int = Query(default=0, ge=0),
):
    return repository.listar_processos(
        orgao_id=orgao_id, status_atual=status_atual, limite=limite, offset=offset
    )


@router.get("/{processo_id}", response_model=ProcessoOut)
def buscar_processo(processo_id: int):
    processo = repository.buscar_processo_por_id(processo_id)
    if not processo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado.")
    return processo


@router.get("/{processo_id}/movimentacoes", response_model=List[MovimentacaoOut])
def listar_movimentacoes(processo_id: int):
    processo = repository.buscar_processo_por_id(processo_id)
    if not processo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado.")
    return repository.listar_movimentacoes_do_processo(processo_id)
