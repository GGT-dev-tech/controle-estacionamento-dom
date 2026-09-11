import asyncio
import os
import sys

# Ajustar o path para poder importar módulos do app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.vaga import Vaga

# Lista exata das 8 vagas que extraímos dos seus arquivos HTML antigos
VAGAS_REAIS = [
    {"numero": "49", "posicao": "Normal", "andar": "S2", "tipo": "padrao"},
    {"numero": "49-A", "posicao": "VAGA DE TRÁS", "andar": "S2", "tipo": "presa"},
    {"numero": "53", "posicao": "Normal", "andar": "S2", "tipo": "padrao"},
    {"numero": "53-A", "posicao": "PAREDE", "andar": "S2", "tipo": "presa"},
    {"numero": "61", "posicao": "Normal", "andar": "G2", "tipo": "padrao"},
    {"numero": "86", "posicao": "Normal", "andar": "G2", "tipo": "padrao"},
    {"numero": "92", "posicao": "Normal", "andar": "G2", "tipo": "padrao"},
    {"numero": "92-A", "posicao": "VAGA DE TRÁS", "andar": "G2", "tipo": "presa"},
]

async def seed_vagas():
    async with SessionLocal() as db:
        print("Iniciando o cadastro das vagas reais...")
        adicionadas = 0
        
        for v in VAGAS_REAIS:
            vaga_id = f"VAGA-{v['numero']}"
            vaga_existente = await db.get(Vaga, vaga_id)
            if not vaga_existente:
                nova_vaga = Vaga(
                    id=vaga_id,
                    numero=v['numero'],
                    andar=v['andar'],
                    posicao=v['posicao'],
                    tipo=v['tipo']
                )
                db.add(nova_vaga)
                adicionadas += 1
                print(f"✅ Vaga {v['numero']} adicionada.")
            else:
                print(f"⚠️ Vaga {v['numero']} já existe.")
                
        if adicionadas > 0:
            await db.commit()
            print(f"\n🎉 Sucesso! {adicionadas} vagas reais cadastradas no banco de produção.")
        else:
            print("\nNenhuma vaga nova adicionada.")

if __name__ == "__main__":
    asyncio.run(seed_vagas())
