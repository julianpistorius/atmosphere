import collections

import datetime
import django
from dateutil.parser import parse
from django import db, conf

from jetstream import stream_logic

conf.settings.DEBUG = True
conf.settings.SEND_EMAILS = False

django.setup()

# end_date = parse('2016-09-01 00:00:00.0-05')
# end_date = parse('2016-10-01 00:00:00.0-05')
# end_date = parse('2016-11-01 00:00:00.0-05')
end_date = parse('2016-12-01 00:00:00.0-05')
print 'end_date: ', end_date

db.reset_queries()

accumulator = stream_logic.batch_calculate_system_state(end_date=end_date)

assert isinstance(accumulator, stream_logic.Accumulator)

allocations_durations_totals = collections.defaultdict(datetime.timedelta)

for instance_id, instance in accumulator.instances.iteritems():
    assert isinstance(instance, stream_logic.Instance)
    for allocation_name, allocation_duration in instance.allocations_durations.iteritems():
        allocations_durations_totals[allocation_name] += allocation_duration

total_usage = 0.0
total_usage_without_na = 0.0

for allocation_source_id, duration in allocations_durations_totals.iteritems():
    assert isinstance(duration, datetime.timedelta)
    cpu_hours = duration.total_seconds()/3600.0
    print allocation_source_id, cpu_hours
    total_usage += cpu_hours
    if allocation_source_id != 'N/A':
        total_usage_without_na += cpu_hours

print 'total_usage:', total_usage
print 'total_usage_without_na:', total_usage_without_na

total_usage_alt = 0.0
total_usage_without_na_alt = 0.0
for username, user in accumulator.users.iteritems():
    assert isinstance(user, stream_logic.User)
    for allocation_source_id, duration in user.allocations_usage.iteritems():
        assert isinstance(duration, datetime.timedelta)
        cpu_hours = duration.total_seconds() / 3600.0
        total_usage_alt += cpu_hours
        if allocation_source_id != 'N/A':
            total_usage_without_na_alt += cpu_hours

print 'total_usage_alt:', total_usage_alt
print 'total_usage_without_na_alt:', total_usage_without_na_alt

# print '# queries: {}'.format(len(db.connection.queries))
# for query in db.connection.queries:
#     print query

# print 'statuses: {}'.format(accumulator.statuses)
# print 'activities: {}'.format(accumulator.activities)
# print 'active_provider_aliases: {}'.format(accumulator.active_provider_aliases)
# for active_instance in [accumulator.instances[active_provider_aliases] for active_provider_aliases in
#                         accumulator.active_provider_aliases]:
#     print active_instance
