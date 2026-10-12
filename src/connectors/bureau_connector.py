import requests
import constants
from utils.validation import instant, valid_text
from errors import InvalidSchema


class BureauConnector:
    def check(self, customer_type, document_number):
        # No retry adapter, no shared mutable Session and no database access.
        try:
            response = requests.post(constants.BUREAU_URL+'/check', json={'customer_type':customer_type,
                                     'document_number':document_number}, timeout=(3,5))
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get('status') not in ('REGULAR','IRREGULAR','NOT_FOUND'):
                return None
            if type(data.get('has_debt')) is not bool or not valid_text(data.get('reference')) or not 1<=len(data['reference'])<=120:
                return None
            checked = instant(data.get('checked_at'))
            return {'status':data['status'],'has_debt':data['has_debt'],'reference':data['reference'],'checked_at':checked}
        except (requests.RequestException, ValueError, InvalidSchema):
            return None
