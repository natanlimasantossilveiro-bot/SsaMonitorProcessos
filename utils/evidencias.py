import os
import re
from datetime import datetime


PASTA_EVIDENCIAS = "evidencias"


def criar_pasta_evidencias():
    if not os.path.exists(PASTA_EVIDENCIAS):
        os.makedirs(PASTA_EVIDENCIAS)


def limpar_nome_arquivo(texto):
    texto = str(texto)
    texto = re.sub(r"[^\w\-]+", "_", texto)
    return texto.strip("_")


async def salvar_evidencia(page, processo, status, mensagem=None):
    criar_pasta_evidencias()

    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    processo_id = processo.get("id", "sem_id")
    numero_processo = limpar_nome_arquivo(
        processo.get("numero_processo", "sem_numero")
    )

    nome_base = f"{agora}_processo_{processo_id}_{numero_processo}_{status}"

    caminho_png = os.path.join(PASTA_EVIDENCIAS, f"{nome_base}.png")
    caminho_html = os.path.join(PASTA_EVIDENCIAS, f"{nome_base}.html")
    caminho_txt = os.path.join(PASTA_EVIDENCIAS, f"{nome_base}.txt")

    await page.screenshot(
        path=caminho_png,
        full_page=True
    )

    html = await page.content()

    with open(caminho_html, "w", encoding="utf-8") as arquivo:
        arquivo.write(html)

    with open(caminho_txt, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"Processo ID: {processo_id}\n")
        arquivo.write(f"Número processo: {processo.get('numero_processo')}\n")
        arquivo.write(f"Status: {status}\n")
        arquivo.write(f"Mensagem: {mensagem}\n")
        arquivo.write(f"URL: {page.url}\n")

    return {
        "print": caminho_png,
        "html": caminho_html,
        "txt": caminho_txt,
    }