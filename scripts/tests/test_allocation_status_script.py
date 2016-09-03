""" Tests for the calculate_user_allocation_usage function """

from dateutil.parser import parse
from django.test import TestCase

from scripts.allocation_status_script import calculate_user_allocation_usage, calculate_cpu_hours

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

sizes_data = {'24': {'mem': '8192', 'disk': '0', 'cpu': '1'}, '39': {'mem': '16384', 'disk': '0', 'cpu': '2'},
              '38': {'mem': '8192', 'disk': '0', 'cpu': '4'}, '23': {'mem': '4096', 'disk': '0', 'cpu': '1'},
              '108': {'mem': '16384', 'disk': '0', 'cpu': '2'}, '107': {'mem': '8192', 'disk': '0', 'cpu': '2'},
              '42': {'mem': '65536', 'disk': '0', 'cpu': '8'}, '43': {'mem': '65536', 'disk': '0', 'cpu': '16'},
              '40': {'mem': '32768', 'disk': '0', 'cpu': '16'}, '41': {'mem': '49152', 'disk': '0', 'cpu': '8'},
              '122': {'mem': '4096', 'disk': '0', 'cpu': '1'}, '111': {'mem': '32768', 'disk': '0', 'cpu': '4'},
              '110': {'mem': '16384', 'disk': '0', 'cpu': '4'}, '126': {'mem': '98304', 'disk': '0', 'cpu': '16'},
              '124': {'mem': '16384', 'disk': '0', 'cpu': '4'}, '93': {'mem': '16384', 'disk': '0', 'cpu': '4'},
              '92': {'mem': '8192', 'disk': '0', 'cpu': '2'}, '106': {'mem': '8192', 'disk': '0', 'cpu': '1'},
              '94': {'mem': '32768', 'disk': '0', 'cpu': '4'}, '105': {'mem': '4096', 'disk': '0', 'cpu': '1'}}

status_history_test_data = '''instance_id,ih_id,start_date,end_date,status,activity,username,size_id,cpu,mem,disk
22779,98630,2015-12-14T02:32:18-07:00,2015-12-14T02:32:19.632057-07:00,Unknown,,amitj,136,-1,-1,-1
22779,98631,2015-12-14T02:32:19.632057-07:00,2015-12-14T02:33:22.038840-07:00,build,,amitj,23,1,4096,0
22779,98632,2015-12-14T02:33:22.038840-07:00,2015-12-14T02:34:22.544317-07:00,networking,,amitj,23,1,4096,0
22779,98633,2015-12-14T02:34:22.544317-07:00,2015-12-14T02:36:11.560037-07:00,deploying,,amitj,23,1,4096,0
22779,98634,2015-12-14T02:36:11.560037-07:00,2015-12-17T17:56:44.072222-07:00,active,,amitj,23,1,4096,0
22779,99681,2015-12-17T17:56:44.072222-07:00,2016-01-27T14:29:27.114551-07:00,suspended,,amitj,23,1,4096,0
22779,104734,2016-01-27T14:29:27.114551-07:00,2016-01-27T14:30:33.373198-07:00,networking,,amitj,38,4,8192,0
22779,104736,2016-01-27T14:30:33.373198-07:00,2016-01-27T15:09:07.974776-07:00,deploying,,amitj,38,4,8192,0
22779,104748,2016-01-27T15:09:07.974776-07:00,2016-01-27T16:23:29.262009-07:00,active,,amitj,38,4,8192,0
22779,104755,2016-01-27T16:23:29.262009-07:00,2016-04-07T11:06:17.263607-07:00,suspended,,amitj,38,4,8192,0'''


class TestAllocationStatusScript(TestCase):
    """Tests for the allocation_status_script"""

    def setUp(self):
        pass

    def test_calculate_cpu_hours(self):
        """
        Test that calculate_cpu_hours returns the correct values.
        """
        status_history_file_object = StringIO.StringIO(status_history_test_data)

        # Test Dates
        small_instance_period = ('2015-12-14T02:32:18-07:00', '2016-01-27T14:29:27.114551-07:00')
        large_instance_period = (small_instance_period[1], '2016-04-07T11:06:17.263607-07:00')
        total_instance_period = (small_instance_period[0], large_instance_period[1])

        # Step 1: Run the calculation over the period when the instance was small (size: 23)
        small_report_start_date = parse(small_instance_period[0])
        small_report_end_date = parse(small_instance_period[1])

        small_allocation_usage, small_user_instance_history_data, small_sizes = calculate_user_allocation_usage(
            status_history_file_object,
            small_report_start_date,
            small_report_end_date)

        # Step 2: Run the calculation over the period when the instance was large (size: 38)
        status_history_file_object.seek(0)

        large_report_start_date = parse(large_instance_period[0])
        large_report_end_date = parse(large_instance_period[1])

        large_allocation_usage, large_user_instance_history_data, large_sizes = calculate_user_allocation_usage(
            status_history_file_object,
            large_report_start_date,
            large_report_end_date)

        # Step 3: Run the calculation over the entire lifetime of the instance
        status_history_file_object.seek(0)

        total_report_start_date = parse(total_instance_period[0])
        total_report_end_date = parse(total_instance_period[1])

        total_allocation_usage, total_user_instance_history_data, total_sizes = calculate_user_allocation_usage(
            status_history_file_object,
            total_report_start_date,
            total_report_end_date)

        # Step 4: Usage from step 1 and step 2 should add up to the total usage from step 3

        assert len(small_allocation_usage['amitj']) == 1
        assert len(large_allocation_usage['amitj']) == 1
        assert len(total_allocation_usage['amitj']) == 2

        assert len(small_sizes) == 1
        assert len(large_sizes) == 1
        assert len(total_sizes) == 2
        assert set(total_sizes.keys()) == set(small_sizes.keys() + large_sizes.keys())

        small_cpu_count = small_sizes['23']['cpu']
        assert small_cpu_count == '1'
        large_cpu_count = large_sizes['38']['cpu']
        assert large_cpu_count == '4'

        expected_small_seconds = 314432.512185
        expected_small_cpu_hours = expected_small_seconds / 3600 * int(small_cpu_count)
        expected_large_seconds = 4461.287233
        expected_large_cpu_hours = expected_large_seconds / 3600 * int(large_cpu_count)
        expected_total_cpu_hours = expected_small_cpu_hours + expected_large_cpu_hours

        assert expected_small_seconds == small_allocation_usage['amitj']['23'] == total_allocation_usage['amitj']['23']
        assert expected_large_seconds == large_allocation_usage['amitj']['38'] == total_allocation_usage['amitj']['38']

        small_user_cpu_hours = calculate_cpu_hours(small_allocation_usage, total_sizes)
        large_user_cpu_hours = calculate_cpu_hours(large_allocation_usage, total_sizes)
        total_user_cpu_hours = calculate_cpu_hours(total_allocation_usage, total_sizes)

        assert expected_small_cpu_hours == small_user_cpu_hours['amitj']
        assert expected_large_cpu_hours == large_user_cpu_hours['amitj']
        assert round(expected_total_cpu_hours - total_user_cpu_hours['amitj'], 5) == 0
