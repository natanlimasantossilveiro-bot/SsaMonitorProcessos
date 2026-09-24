from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class OrgaoOut(BaseModel):
    id: int
    nome: str
    tipo: Optional[str] = None
    url: Optional[str] = None
    chave_robo: Optional[str] = None
    possui_login: Optional[bool] = None
    possui_captcha: Optional[bool] = None
    ativo: Optional[bool] = None


class ProcessoOut(BaseModel):
    id: int
    orgao_id: int
    numero_processo: Optional[str] = None
    empresa: Optional[str] = None
    cnpj: Optional[str] = None
    municipio: Optional[str] = None
    exercicio: Optional[str] = None
    codigo: Optional[str] = None
    status_processo: Optional[str] = None
    status_atual: Optional[str] = None
    data_ultimo_movimento: Optional[date] = None
    ultima_movimentacao: Optional[str] = None
    ultima_consulta: Optional[datetime] = None
    ativo: Optional[bool] = None
    nome_orgao: Optional[str] = None
    monitorado: Optional[bool] = None
    ultimo_resultado: Optional[str] = None


class MovimentacaoOut(BaseModel):
    id: int
    processo_id: int
    data_movimento: Optional[date] = None
    descricao: Optional[str] = None
