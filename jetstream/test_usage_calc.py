import StringIO
import csv
import pprint
import sys
import time

from django import db, test, conf, template

from core.models import allocation_source

# This is from Jetstream database
DB_QUERIES_INFO_TEMPLATE = '''{{count}} quer{{count|pluralize:"y,ies"}} in {{time}} seconds:

{% for sql in sqllog %}[{{forloop.counter}}] {{sql.time}}s: {{sql.sql|safe}}{% if not forloop.last %}

{% endif %}{% endfor %}'''

USER_ALLOCATION_SNAPSHOT_DATA = '''allocation_source_name,username,compute_used,burn_rate,updated
TG-ASC150011,tkchafin,78313.870,4.000,2016-10-06 10:21:16.788832-07
TG-BIO160058,tkchafin,71502.230,4.000,2016-10-06 09:58:45.041793-07
TG-CDA160007,tkchafin,54401.830,4.000,2016-10-06 10:17:01.717362-07
TG-BIO150062,upendra,48403.380,11.000,2016-10-06 10:01:58.329387-07
TG-ASC160018,amercer,43288.750,2.000,2016-10-06 10:22:11.743773-07
CH-816862,mpackard,12182.950,4.000,2016-10-06 09:54:45.590125-07
TG-BIO160012,vbrendel,10496.860,2.000,2016-10-06 10:19:37.220624-07
TG-MCB160143,hokim1,8588.070,3.000,2016-10-06 10:22:15.178781-07
TG-BIO150062,nirav,7932.260,3.000,2016-10-06 10:00:36.168854-07
TG-MCB140255,emre,5820.700,2.000,2016-10-06 10:12:05.150609-07
'''

USE_FAKE_NUMBERS = True


# example_data_query = '''COPY (SELECT als.name AS allocation_source_name, au.username, uas.compute_used, uas.burn_rate,
#  uas.updated
# FROM user_allocation_snapshot uas
#   LEFT JOIN allocation_source als ON uas.allocation_source_id = als.id
#   LEFT JOIN atmosphere_user au ON uas.user_id = au.id
# ORDER BY compute_used DESC
# LIMIT 10) TO '/tmp/uas.csv' WITH CSV HEADER DELIMITER ',';
# '''


class LoggingTestCase(test.TestCase):
    @staticmethod
    def setUpClass():
        # The test runner sets DEBUG to False. Set to True to enable SQL logging.
        conf.settings.DEBUG = True
        super(LoggingTestCase, LoggingTestCase).setUpClass()

    @staticmethod
    def tearDownClass():
        super(LoggingTestCase, LoggingTestCase).tearDownClass()

        time = sum([float(q['time']) for q in db.connection.queries])
        t = template.Template(
            DB_QUERIES_INFO_TEMPLATE)
        print >> sys.stderr, t.render(template.Context({
            'sqllog': db.connection.queries,
            'count': len(db.connection.queries),
            'time': time}))

        # Empty the query list between TestCases.
        db.reset_queries()


class TestJetstreamUsageCalc(LoggingTestCase):
    """Tests for Jetstream usage calculation"""

    def test_basic_calc(self):
        # Find an allocation source
        start_date = '2016-09-01 00:00:00.0-05'
        examples = csv.DictReader(StringIO.StringIO(USER_ALLOCATION_SNAPSHOT_DATA))

        for example in examples:
            pprint.pprint(example)
            if USE_FAKE_NUMBERS:
                compute_used_slow = 67942.5
                burn_rate_slow = 4
                duration_slow = 11.9380331039
            else:
                # Run calculation
                start_time = time.time()
                compute_used_slow, burn_rate_slow = allocation_source.total_usage(example['username'],
                                                                                  start_date,
                                                                                  example['allocation_source_name'],
                                                                                  end_date=example['updated'],
                                                                                  burn_rate=True)
                end_time = time.time()
                duration_slow = end_time - start_time
            print('SLOW compute_used: {}'.format(compute_used_slow))
            print('SLOW burn_rate: {}'.format(burn_rate_slow))
            print('SLOW duration: {} seconds'.format(duration_slow))

            start_time = time.time()
            compute_used_fast, burn_rate_fast = allocation_source.total_usage_fast(example['username'],
                                                                                   start_date,
                                                                                   example['allocation_source_name'],
                                                                                   end_date=example['updated'],
                                                                                   burn_rate=True)
            end_time = time.time()
            duration_fast = end_time - start_time
            print('FAST compute_used: {}'.format(compute_used_fast))
            print('FAST burn_rate: {}'.format(burn_rate_fast))
            print('FAST duration: {} seconds'.format(duration_fast))

            speedup_ratio = duration_slow / duration_fast
            print('pre/post: {}'.format(speedup_ratio))

            self.assertEqual(compute_used_slow, compute_used_fast)
            self.assertEqual(burn_rate_slow, burn_rate_fast)
            # break
        pass
