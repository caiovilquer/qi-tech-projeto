from sqlalchemy import select, text
from models import metadata


class HealthRepository:
    def __init__(self, context):
        self.session = context.db_session

    def check(self):
        self.session.execute(text('SELECT 1')).scalar_one()
        for table in metadata.sorted_tables:
            self.session.execute(select(table).limit(0))
