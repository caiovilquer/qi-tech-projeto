from controllers.account_controller import AccountController
from controllers.transaction import db_action, commit
from repositories.operation_repository import OperationRepository
from errors import BankingError, InvalidParameter
from utils.validation import uuid_value, instant
from dtos.banking_dto import operation_detail_dto, statement_dto
from utils.pix_window import pix_window
import constants


class OperationController(AccountController):
    @db_action
    def write(self, account_key, context_key, payload, key, kind):
        owner=self.customer(context_key)
        own=self.authorize(account_key,owner)
        if kind=='TRANSFER':
            destination=self.repository.by_key(payload['destination_account_key'])
            if destination is None: raise BankingError('QIT001026')
            if own['id']==destination['id']: raise BankingError('QIT001010')
            origin=own
            modality=payload['modality']
            fee=constants.FEES[owner['customer_type'],modality]
        else:
            origin=None; destination=own; modality=None; fee=0
        values={'customer_id':owner['id'],'type':kind,'modality':modality,
                'origin_account_id':origin['id'] if origin else None,'destination_account_id':destination['id'],
                'amount_cents':payload['amount_cents'],'fee_cents':fee,'idempotency_key':key}
        repo=OperationRepository(self.context)
        operation=repo.reserve(values)
        if operation is None:
            existing=repo.replay(owner['id'],key)  # fresh READ COMMITTED command
            if any(existing[k]!=values[k] for k in ['type','modality','origin_account_id','destination_account_id','amount_cents']):
                raise BankingError('QIT001012')
            self.context.operation_key=existing['operation_key']
            self.context.outcome='replay'
            self.session.rollback()
            return {'operation_key':existing['operation_key']}
        self.context.operation_key=operation['operation_key']
        if modality=='PIX_SIMULATED':
            repo.lock_customer(owner['id'])
        rows={r['id']:r for r in self.repository.lock([destination['id']]+([origin['id']] if origin else []))}
        destination=rows[destination['id']]
        origin=rows[origin['id']] if origin else None
        timestamp=repo.financial_time()  # once, only after every lock
        repo.timestamp(operation['id'],timestamp)
        amount=payload['amount_cents']
        if kind=='DEPOSIT' and not constants.SANDBOX_DEPOSITS:
            raise BankingError('QIT001035')
        if destination['status'] not in ('ACTIVE','BLOCKED') or (origin and origin['status']!='ACTIVE'):
            raise BankingError('QIT001029')
        if origin and origin['balance_cents']<amount+fee:
            raise BankingError('QIT001011')
        if destination['balance_cents']+amount>constants.MAX_CENTS:
            raise BankingError('QIT001013')
        if modality=='PIX_SIMULATED':
            start,end,quota=pix_window(timestamp)
            if repo.pix_consumed(owner['id'],start,end)+amount>quota:
                raise BankingError('QIT001032')
        if origin:
            after=repo.delta(operation['id'],origin['id'],-amount,'TRANSFER_DEBIT',timestamp)
            assert after==origin['balance_cents']-amount
            if fee:
                fee_after=repo.delta(operation['id'],origin['id'],-fee,'FEE_DEBIT',timestamp)
                assert fee_after==after-fee
        after=repo.delta(operation['id'],destination['id'],amount,'TRANSFER_CREDIT' if origin else 'DEPOSIT_CREDIT',timestamp)
        assert after==destination['balance_cents']+amount
        result={'operation_key':operation['operation_key']}
        commit(self)
        return result

    @db_action
    def detail(self, account_key, context_key, key):
        owner=self.customer(context_key)
        own=self.authorize(account_key,owner)
        op,entries=OperationRepository(self.context).detail(own['id'],key)
        if not entries: raise BankingError('QIT001028')
        return operation_detail_dto(op, own['account_key'], entries)

    @db_action
    def statement(self, account_key, context_key, limit, cursor, filters):
        owner=self.customer(context_key)
        own=self.authorize(account_key,owner)
        dates={k:instant(v) if v is not None else None for k,v in filters.items()}
        if dates.get('from') and dates.get('to') and dates['from']>=dates['to']:
            raise InvalidParameter('Start must precede end')
        cursor=uuid_value(cursor,cursor=True) if cursor is not None else None
        rows=OperationRepository(self.context).statement(own['id'],limit,cursor,dates)
        if rows is None: raise BankingError('QIT001033')
        return statement_dto(rows, limit)
