class WealthAdvisorError(Exception):
    """Base class for all domain errors in the wealth advisor system."""


class ClientDataValidationError(WealthAdvisorError):
    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"{source}: {message}")
