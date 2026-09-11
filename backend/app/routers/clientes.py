import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cliente import Cliente
from app.models.ocupante import TipoCliente
from app.models.veiculo import Veiculo
from app.schemas.cliente import (
    MeuCadastroCreate,
    MeuCadastroRead,
    MeuCadastroUpdate,
    VeiculoCreate,
    VeiculoRead,
)
from app.security.auth import get_current_user
from app.services.whatsapp import enviar_mensagem, normalizar_telefone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clientes", tags=["Clientes"])


async def _montar_meu_cadastro(db: AsyncSession, cliente: Cliente) -> MeuCadastroRead:
    veiculos = (
        await db.execute(select(Veiculo).where(Veiculo.cliente_id == cliente.id).order_by(Veiculo.criado_em))
    ).scalars().all()
    return MeuCadastroRead(
        id=cliente.id,
        nome=cliente.nome,
        telefone=cliente.telefone,
        email=cliente.email,
        tipo_cliente=cliente.tipo_cliente,
        ativo=cliente.ativo,
        criado_em=cliente.criado_em,
        veiculos=[VeiculoRead.model_validate(v) for v in veiculos],
    )


async def _obter_meu_cliente(db: AsyncSession, sub: str) -> Cliente:
    cliente = (await db.execute(select(Cliente).where(Cliente.auth0_sub == sub))).scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado.")
    return cliente


@router.get("/me", response_model=MeuCadastroRead)
async def obter_meu_cadastro(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> MeuCadastroRead:
    """404 é o sinal que o frontend usa para saber que é o primeiro acesso do usuário."""
    cliente = await _obter_meu_cliente(db, user["sub"])
    return await _montar_meu_cadastro(db, cliente)


@router.post("/me", response_model=MeuCadastroRead, status_code=201)
async def criar_meu_cadastro(
    payload: MeuCadastroCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> MeuCadastroRead:
    if (await db.execute(select(Cliente).where(Cliente.auth0_sub == user["sub"]))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Cadastro já existe.")

    telefone = normalizar_telefone(payload.telefone)
    existente = (await db.execute(select(Cliente).where(Cliente.telefone == telefone))).scalar_one_or_none()

    if existente:
        if existente.auth0_sub and existente.auth0_sub != user["sub"]:
            raise HTTPException(status_code=409, detail="Este telefone já está associado a outro cadastro.")
        # Adota um cadastro criado manualmente pelo admin (sem auth0_sub ainda) em vez de duplicar.
        existente.auth0_sub = user["sub"]
        existente.nome = payload.nome
        existente.email = payload.email
        cliente = existente
    else:
        cliente = Cliente(
            nome=payload.nome,
            telefone=telefone,
            email=payload.email,
            tipo_cliente=TipoCliente.rotativo,
            auth0_sub=user["sub"],
        )
        db.add(cliente)

    await db.commit()
    await db.refresh(cliente)

    await enviar_mensagem(
        telefone,
        "👋 Bem-vindo(a) ao Dom Estacionamento! Seu cadastro foi concluído — "
        "envie */ajuda* aqui no WhatsApp pra ver os comandos disponíveis.",
    )

    return await _montar_meu_cadastro(db, cliente)


@router.patch("/me", response_model=MeuCadastroRead)
async def atualizar_meu_cadastro(
    payload: MeuCadastroUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> MeuCadastroRead:
    cliente = await _obter_meu_cliente(db, user["sub"])
    dados = payload.model_dump(exclude_unset=True)
    
    telefone_antigo = cliente.telefone
    telefone_novo = None
    
    if "telefone" in dados and dados["telefone"] is not None:
        telefone_novo = normalizar_telefone(dados["telefone"])
        dados["telefone"] = telefone_novo
        
    for campo, valor in dados.items():
        setattr(cliente, campo, valor)
        
    await db.commit()
    await db.refresh(cliente)
    
    if telefone_novo and telefone_novo != telefone_antigo:
        await enviar_mensagem(
            telefone_novo,
            "📱 Seu número foi atualizado no Dom Estacionamento com sucesso! "
            "Sempre que precisar, envie */ajuda* aqui para ver os comandos do bot de reservas."
        )
        
    return await _montar_meu_cadastro(db, cliente)


@router.post("/me/veiculos", response_model=VeiculoRead, status_code=201)
async def adicionar_meu_veiculo(
    payload: VeiculoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Veiculo:
    cliente = await _obter_meu_cliente(db, user["sub"])
    placa = payload.placa.strip().upper() if payload.placa else None
    if placa and (await db.execute(select(Veiculo).where(Veiculo.placa == placa))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Já existe um veículo cadastrado com esta placa.")
    veiculo = Veiculo(cliente_id=cliente.id, placa=placa, veiculo=payload.veiculo)
    db.add(veiculo)
    await db.commit()
    await db.refresh(veiculo)
    return veiculo


@router.delete("/me/veiculos/{veiculo_id}", status_code=204)
async def remover_meu_veiculo(
    veiculo_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> None:
    cliente = await _obter_meu_cliente(db, user["sub"])
    veiculo = await db.get(Veiculo, veiculo_id)
    if not veiculo or veiculo.cliente_id != cliente.id:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")
    await db.delete(veiculo)
    await db.commit()
