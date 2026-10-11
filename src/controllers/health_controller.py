from controllers.base_controller import BaseController
from repositories.health_repository import HealthRepository
from errors import BankingError
from sqlalchemy.exc import SQLAlchemyError


class HealthController(BaseController):
    def readiness(self):
        try:
            HealthRepository(self.context).check()
        except SQLAlchemyError:
            raise BankingError('QIT001014')
        finally:
            self.session.rollback()
