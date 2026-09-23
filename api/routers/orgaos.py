from typing import List

from fastapi import APIRouter, Depends

from api import repository
from api.auth import verificar_token
from api.schemas import OrgaoOut

router = APIRouter(prefix="/orgaos", tags=["orgaos"], dependencies=[Depends(verificar_token)])


@router.get("", response_model=List[OrgaoOut])
def listar_orgaos():
    return repository.listar_orgaos()
