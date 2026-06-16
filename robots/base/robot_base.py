class RobotBase:

    async def consultar_processo(self, processo):
        raise NotImplementedError(
            "O robô deve implementar o método consultar_processo."
        )