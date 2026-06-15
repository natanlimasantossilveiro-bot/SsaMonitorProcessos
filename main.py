import os
import asyncio

from services.importador_planilha_service import importar_planilha_base

from services.monitoramento_service import (
    validar_orgaos_importados,
    monitorar_processos_ativos,
    monitorar_um_processo_teste,
)


def importar_planilha():
    resultado = importar_planilha_base("Planilha_Base.xlsx")

    print("\n=== IMPORTAÇÃO DA PLANILHA ===")
    print(f"Total de linhas lidas: {resultado['total_linhas']}")
    print(f"Total importados/atualizados: {resultado['total_importados']}")
    print(f"Total ignorados: {resultado['total_ignorados']}")
    print(f"Sem robô configurado: {resultado['sem_robo']}")


def abrir_pasta_relatorios():
    pasta = "relatorios"

    if not os.path.exists(pasta):
        os.makedirs(pasta)

    os.startfile(os.path.abspath(pasta))


def abrir_pasta_evidencias():
    pasta = "evidencias"

    if not os.path.exists(pasta):
        os.makedirs(pasta)

    os.startfile(os.path.abspath(pasta))


def exibir_menu():
    print("\n=== SSA MONITOR PROCESSOS ===")
    print("1 - Importar planilha base")
    print("2 - Validar órgãos/links importados")
    print("3 - Monitorar todos os processos ativos")
    print("4 - Monitorar apenas 1 processo para teste")
    print("5 - Abrir pasta de relatórios")
    print("6 - Abrir pasta de evidências")
    print("0 - Sair")

    return input("\nEscolha uma opção: ").strip()


async def main():
    while True:
        opcao = exibir_menu()

        if opcao == "1":
            importar_planilha()

        elif opcao == "2":
            validar_orgaos_importados()

        elif opcao == "3":
            await monitorar_processos_ativos()

        elif opcao == "4":
            await monitorar_um_processo_teste()

        elif opcao == "5":
            abrir_pasta_relatorios()

        elif opcao == "6":
            abrir_pasta_evidencias()

        elif opcao == "0":
            print("\nEncerrando sistema...")
            break

        else:
            print("\nOpção inválida. Tente novamente.")


if __name__ == "__main__":
    asyncio.run(main())