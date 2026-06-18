CAMPO_CAPTCHA = None

CAMPOS_NUMERO_POSSIVEIS = [
    "input[name='numero']",
    "input[id*='numero' i]",
    "input[placeholder*='número' i]",
    "input[placeholder*='numero' i]",
    "input[type='text']",
]

CAMPOS_ANO_POSSIVEIS = [
    "input[name='ano']",
    "input[name='exercicio']",
    "input[id*='ano' i]",
    "input[id*='exercicio' i]",
    "input[placeholder*='ano' i]",
    "input[placeholder*='exercício' i]",
    "input[placeholder*='exercicio' i]",
]

CAMPOS_CODIGO_VERIFICADOR_POSSIVEIS = [
    "input[name='codigo_verificador']",
    "input[name*='codigo' i]",
    "input[id*='codigo' i]",
    "input[placeholder*='código' i]",
    "input[placeholder*='codigo' i]",
    "input[placeholder*='verificador' i]",
]

BOTOES_CONFIRMAR_POSSIVEIS = [
    "button[name='confirmar']",
    "button:has-text('Confirmar')",
    "button:has-text('Consultar')",
    "button:has-text('Pesquisar')",
    "input[type='submit']",
]

BOTAO_LIMPAR = "button:has-text('Limpar')"

TEXTO_CAPTCHA = "Verificação de acesso"