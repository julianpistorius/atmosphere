import django
from dateutil.parser import parse
from django import db, conf

conf.settings.DEBUG = True

django.setup()

import core.models.allocation_source  # noqa: E402

db.reset_queries()

allocation_source = core.models.allocation_source.AllocationSource.objects.filter(name='TG-ASC160018').first()

user_allocation_source = allocation_source.users.filter(user__username='julianp').first()

user = user_allocation_source.user

start_date = user.date_joined
# end_date = django_utils.timezone.now()
end_date = parse('2016-11-01 22:51:28.533939-04')

db.reset_queries()
# print db.connection.queries

# %time compute_used, burn_rate = total_usage(user.username, start_date, allocation_source_name=allocation_source.name,\
# end_date=end_date, burn_rate=True)
compute_used, burn_rate = core.models.allocation_source.total_usage(user.username, start_date,
                                                                    allocation_source_name=allocation_source.name,
                                                                    end_date=end_date, burn_rate=True)

print 'compute_used: {}'.format(compute_used)
print 'burn_rate: {}'.format(burn_rate)

# CPU times: user 716 ms, sys: 48 ms, total: 764 ms
# Wall time: 19.8 s

print '# queries: {}'.format(len(db.connection.queries))
