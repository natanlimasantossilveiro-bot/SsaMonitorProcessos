def gerar_linhas_tabela(lista, colunas):

    if not lista:
        return f"""
            <tr>
                <td colspan="{len(colunas)}">
                    Nenhum registro encontrado.
                </td>
            </tr>
        """

    html = ""

    for item in lista:

        html += "<tr>"

        for coluna in colunas:

            valor = item.get(coluna)

            if valor is None:
                valor = ""

            html += f"<td>{valor}</td>"

        html += "</tr>"

    return html