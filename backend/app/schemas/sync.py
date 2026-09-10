from typing import Any, Literal

from pydantic import BaseModel

TipoOperacaoPendente = Literal["entrada", "saida", "reserva", "cancelamento"]


class OperacaoPendente(BaseModel):
    id: int  # id local (Dexie/IndexedDB) — devolvido para o cliente marcar como sincronizada
    tipo: TipoOperacaoPendente
    payload: dict[str, Any]


class SincronizarRequest(BaseModel):
    operacoes: list[OperacaoPendente]


class ResultadoOperacao(BaseModel):
    id: int
    sucesso: bool
    mensagem: str | None = None


class SincronizarResponse(BaseModel):
    resultados: list[ResultadoOperacao]
