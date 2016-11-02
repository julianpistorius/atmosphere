import django
from dateutil.parser import parse
from django import db, conf

from jetstream import stream_logic

conf.settings.DEBUG = True

django.setup()

end_date = parse('2016-11-02 22:51:28.533939-04')

db.reset_queries()

accumulator = stream_logic.batch_calculate_system_state(end_date=end_date)

assert isinstance(accumulator, stream_logic.Accumulator)

for instance_id, instance in accumulator.instances.iteritems():
    # print(instance)
    pass

print '# queries: {}'.format(len(db.connection.queries))
# for query in db.connection.queries:
#     print query

# print 'statuses: {}'.format(accumulator.statuses)
# print 'activities: {}'.format(accumulator.activities)
# print 'active_instance_ids: {}'.format(accumulator.active_instance_ids)
# for active_instance in [accumulator.instances[active_instance_id] for active_instance_id in
#                         accumulator.active_instance_ids]:
#     print active_instance
# print accumulator.instances_missing
# missing_instances = collections.Counter([accumulator.instances.get(missing_instance_id) for missing_instance_id in
#                                          accumulator.instances_missing])
# print missing_instances

for username, user in accumulator.users.iteritems():
    print user
