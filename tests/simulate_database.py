from pydantic import model_validator

from config_wrangler.config_templates.credentials import Credentials

class SimDatabase(Credentials):
    """
    Like SQLAlchemyDatabase but does not require sqlalchemy to be installed
    """
    dialect: str

    @model_validator(mode='after')
    def check_model(self):
        if self.dialect == 'sqlite':
            # Bypass password checks
            return self
        else:
            # noinspection PyCallingNonCallable
            return Credentials.check_model(self)

    def get_password(self) -> str:
        try:
            return super().get_password()
        except ValueError:
            if self.dialect not in {'sqlite'}:
                raise
            else:
                # noinspection PyTypeChecker
                return None
