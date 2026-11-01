"""Cria o primeiro administrador: python -m app.criar_admin <email> <nome>.

A senha é pedida no terminal.
"""

import getpass
import sys

from app.db import SessionLocal
from app.models import Perfil, Usuario
from app.schemas.auth import UsuarioCriar
from app.security import gerar_hash


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dados = UsuarioCriar(
        email=sys.argv[1], nome=sys.argv[2], senha=getpass.getpass("Senha: "), perfil=Perfil.ADMIN
    )
    with SessionLocal() as db:
        db.add(
            Usuario(
                nome=dados.nome,
                email=dados.email.lower(),
                senha_hash=gerar_hash(dados.senha),
                perfil=dados.perfil,
            )
        )
        db.commit()
    print(f"Administrador {dados.email} criado.")


if __name__ == "__main__":
    main()
