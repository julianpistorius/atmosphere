import django
from dateutil.parser import parse
from django import db, conf

conf.settings.DEBUG = True

django.setup()

import core.models.allocation_source  # noqa: E402
from service import allocation_logic  # noqa: E402

db.reset_queries()

allocation_source = core.models.allocation_source.AllocationSource.objects.filter(name='TG-ASC160018').first()

start_date = parse('2016-01-01 22:51:28.533939-04')
end_date = parse('2016-11-01 22:51:28.533939-04')

db.reset_queries()

data = allocation_logic.create_report(start_date, end_date)

print 'len(data): {}'.format(len(data))

for row in data:
    print row

# CPU times: user 716 ms, sys: 48 ms, total: 764 ms
# Wall time: 19.8 s

print '# queries: {}'.format(len(db.connection.queries))
