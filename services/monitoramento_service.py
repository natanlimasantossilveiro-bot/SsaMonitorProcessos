from database.repositories import (
    listar_orgaos,
    listar_processos_ativos_com_orgao,
    registrar_historico_consulta,
)

from robots.curitiba.robot import consultar_processo_curitiba


STATUS_SEM_ROBO_CONFIGURADO = "SEM_ROBO_CONFIGURADO"
STATUS_ERRO_CONSULTA = "ERRO_CONSULTA"


def validar_orgaos_importados():
    orgaos = listar_orgaos()

    print("\n=== ÓRGÃOS / LINKS IMPORTADOS ===")

    if not orgaos:
        print("Nenhum órgão encontrado no banco.")
        return

    for orgao in orgaos:
        print("\n----------------------------------------")
        print(f"ID: {orgao.get('id')}")
        print(f"Nome: {orgao.get('nome')}")
        print(f"Tipo: {orgao.get('tipo')}")
        print(f"URL: {orgao.get('url')}")
        print(f"Chave robô: {orgao.get('chave_robo')}")


async def monitorar_processos_ativos():
    processos = listar_processos_ativos_com_orgao()

    print("\n=== MONITORAMENTO DE PROCESSOS ATIVOS ===")
    print(f"Total de processos encontrados: {len(processos)}")

    if not processos:
        print("Nenhum processo ativo encontrado.")
        return

    for processo in processos:
        await rotear_consulta_processo(processo)


async def monitorar_um_processo_teste():
    processos = listar_processos_ativos_com_orgao()

    if not processos:
        print("\nNenhum processo ativo encontrado para teste.")
        return

    print("\n=== PROCESSOS DISPONÍVEIS PARA TESTE ===")

    for indice, processo in enumerate(processos, start=1):
        print(
            f"{indice} - "
            f"{processo.get('numero_processo')} | "
            f"{processo.get('empresa')} | "
            f"{processo.get('nome_orgao')} | "
            f"Robô: {processo.get('chave_robo')}"
        )

    escolha = input("\nDigite o número do processo para testar: ").strip()

    if not escolha.isdigit():
        print("Opção inválida.")
        return

    indice_escolhido = int(escolha)

    if indice_escolhido < 1 or indice_escolhido > len(processos):
        print("Processo não encontrado na lista.")
        return

    processo = processos[indice_escolhido - 1]

    await rotear_consulta_processo(processo)


async def rotear_consulta_processo(processo):
    processo_id = processo.get("id")
    numero_processo = processo.get("numero_processo")
    chave_robo = processo.get("chave_robo")

    print("\n========================================")
    print(f"Processo ID: {processo_id}")
    print(f"Número: {numero_processo}")
    print(f"Empresa: {processo.get('empresa')}")
    print(f"Município: {processo.get('municipio')}")
    print(f"Órgão: {processo.get('nome_orgao')}")
    print(f"Robô: {chave_robo}")

    if chave_robo == "curitiba":
        try:
            resultado = await consultar_processo_curitiba(processo)

            status = resultado.get("status", "OK")
            mensagem = resultado.get("mensagem", "")

            registrar_historico_consulta(
                processo_id=processo_id,
                status=status,
                mensagem=mensagem,
            )

            print(f"Status final: {status}")
            return resultado

        except Exception as erro:
            mensagem = str(erro)

            registrar_historico_consulta(
                processo_id=processo_id,
                status=STATUS_ERRO_CONSULTA,
                mensagem=mensagem,
            )

            print(f"Erro ao consultar processo: {mensagem}")

            return {
                "status": STATUS_ERRO_CONSULTA,
                "mensagem": mensagem,
            }

    registrar_historico_consulta(
        processo_id=processo_id,
        status=STATUS_SEM_ROBO_CONFIGURADO,
        mensagem=f"Não existe robô configurado para a chave: {chave_robo}",
    )

    print("Status final: SEM_ROBO_CONFIGURADO")

    return {
        "status": STATUS_SEM_ROBO_CONFIGURADO,
        "mensagem": f"Não existe robô configurado para a chave: {chave_robo}",
    }