class CaptchaSolverBase:

    async def resolver_captcha(self, page):
        raise NotImplementedError("Resolver captcha não implementado")