"""Generate/check bootstrap SQL from models. Run inside the API image."""
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from models import metadata

dialect = postgresql.dialect()
print('-- RFC v8: generated from src/models/banking.py; bootstrap for NEW volumes only.')
for table in metadata.sorted_tables:
    print('\n'.join(line.rstrip() for line in str(CreateTable(table).compile(dialect=dialect)).strip().splitlines()) + ';')
    for index in sorted(table.indexes, key=lambda i: i.name):
        print(str(CreateIndex(index).compile(dialect=dialect)) + ';')
