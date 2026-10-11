from controllers.base_controller import BaseController
from controllers.transaction import db_action, commit
from repositories.account_repository import AccountRepository
from repositories.customer_repository import CustomerRepository
from connectors.bureau_connector import BureauConnector
from dtos.banking_dto import account_dto
from errors import BankingError
from constants import INTEGRATOR_ID


class AccountController(BaseController):
    def __init__(self):
        super().__init__('accounts')
        self.repository = AccountRepository(self.context)

    def customer(self, key):
        row=CustomerRepository(self.context).by_key(key)
        if row is None:
            raise BankingError('QIT001008')
        return row

    def authorize(self, key, customer):
        row=self.repository.by_key(key)
        if row is None or row['customer_id'] != customer['id']:
            raise BankingError('QIT001009')
        return row

    def close_session(self):
        self.session.close()
        self.context.db_session = None

    def opening_result(self, row):
        event=self.repository.opening_event(row['id'])
        if event['new_status']=='REJECTED':
            raise BankingError('QIT001030',row['account_key'])
        return {'account_key':row['account_key'],'opening_result':'APPROVED'}

    @db_action
    def open(self, payload, context_key, key):
        owner=self.customer(context_key)
        if payload['customer_key'] != context_key:
            raise BankingError('QIT001008')
        row=self.repository.create(owner['id'],payload,key)
        if row is None:
            row=self.repository.creation(key)
            if row['creation_request'] != payload:
                raise BankingError('QIT001012')
            if row['status'] != 'PENDING':
                self.context.outcome='replay'
                result=self.opening_result(row)
                self.session.rollback()
                return result
            self.session.rollback()
        else:
            self.repository.event(row,None,'OPENING_REQUESTED',INTEGRATOR_ID)
            commit(self)
        self.close_session()
        bureau=BureauConnector().check(owner['customer_type'],owner['document_number'])
        # A new session, transaction and snapshot only after external HTTP ends.
        self.session=self.context.get_or_create_session()
        self.repository=AccountRepository(self.context)
        row=self.repository.lock([row['id']])[0]
        if row['status'] != 'PENDING':
            self.context.outcome='replay'
            return self.opening_result(row)
        if bureau is None:
            raise BankingError('QIT001031',row['account_key'])
        status='ACTIVE' if bureau['status']=='REGULAR' else 'REJECTED'
        row=self.repository.change(row,status,bureau['status'],'bureau-evaluation',bureau)
        # Build immutable DTO while session is live; response follows commit.
        result={'account_key':row['account_key'],'opening_result':'APPROVED'}
        commit(self)
        if status=='REJECTED':
            raise BankingError('QIT001030',row['account_key'])
        return result

    @db_action
    def get(self, key, context_key):
        owner=self.customer(context_key)
        return account_dto(self.authorize(key,owner),context_key)

    @db_action
    def list(self, context_key, page, limit):
        owner=self.customer(context_key)
        rows=self.repository.list(owner['id'],page,limit)
        return {'data':[account_dto(r,context_key) for r in rows[:limit]],'page':page,'limit':limit,'is_last_page':len(rows)<=limit}

    @db_action
    def status(self, key, context_key, payload):
        owner=self.customer(context_key)
        account=self.authorize(key,owner)
        row=self.repository.lock([account['id']])[0]
        if row['status'] not in ('ACTIVE','BLOCKED'):
            raise BankingError('QIT001029')
        expected=payload['expected_version']; desired=payload['status']; reason=payload['reason']
        if expected==row['status_version']:
            if row['status']!=desired:
                row=self.repository.change(row,desired,reason,INTEGRATOR_ID)
                result={k:row[k] for k in ['account_key','status','status_version']}
                commit(self)
                return result
        elif row['status_version']==expected+1:
            event=self.repository.last_event(row['id'])
            if event['new_status']!=desired or event['reason']!=reason:
                raise BankingError('QIT001034')
        else:
            raise BankingError('QIT001034')
        self.context.outcome='replay'
        return {k:row[k] for k in ['account_key','status','status_version']}
