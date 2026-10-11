"""Controller transaction boundary. Commit errors are conservatively unknown."""
from functools import wraps
from sqlalchemy.exc import DBAPIError, TimeoutError
from errors import BankingError


def db_action(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (DBAPIError, TimeoutError):
            self.session.rollback()
            raise BankingError('QIT001014') from None
        except Exception:
            self.session.rollback()
            raise
    return wrapper


def commit(controller):
    # Flush belongs before the COMMIT boundary. An error here proves this
    # transaction never sent COMMIT, unlike any failure in session.commit().
    controller.session.flush()
    try:
        controller.session.commit()
    except (DBAPIError, TimeoutError):
        controller.context.outcome = 'desconhecido'
        raise BankingError('QIT001027') from None
    controller.context.outcome = 'confirmado'
