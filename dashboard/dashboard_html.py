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

            if coluna in ["status", "status_consulta"]:
                texto = str(valor)

                if "Finalizado" in texto:
                    html += f'<td style="color: green; font-weight: bold;">{valor}</td>'
                elif "Indeferido" in texto:
                    html += f'<td style="color: red; font-weight: bold;">{valor}</td>'
                else:
                    html += f"<td>{valor}</td>"

            else:
                html += f"<td>{valor}</td>"

        html += "</tr>"

    return html