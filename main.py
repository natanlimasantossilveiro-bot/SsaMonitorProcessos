from services.importador_planilha_service import importar_planilha_base


def main():

    resultado = importar_planilha_base(
        "Planilha_Base.xlsx"
    )

    print("\n=== IMPORTAÇÃO DA PLANILHA ===")
    print(f"Total de linhas lidas: {resultado['total_linhas']}")
    print(f"Total importados/atualizados: {resultado['total_importados']}")
    print(f"Total ignorados: {resultado['total_ignorados']}")
    print(f"Sem robô configurado: {resultado['sem_robo']}")


if __name__ == "__main__":
    main()