""" Tests for the calculate_cpu_hours function """
from faker import Faker
from hypothesis import given, settings, strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase

from scripts.allocation_status_script import calculate_cpu_hours

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


def generate_usernames_list(count=10):
    usernames = []
    fake = Faker()
    counter = 0
    while counter < count:
        profile = fake.profile(fields=['username'])
        usernames.append(profile['username'])
        counter += 1
    return usernames


allocations_data = st.dictionaries(keys=st.sampled_from(generate_usernames_list(100)),
                                   values=st.dictionaries(keys=st.sampled_from(sizes_data.keys()),
                                                          values=st.floats(min_value=0.0, allow_infinity=False,
                                                                           allow_nan=False),
                                                          min_size=0, max_size=6),
                                   min_size=10, max_size=200)


class TestAllocationStatusScriptApplicableDuration(HypothesisTestCase):
    with settings(max_examples=1000, perform_health_check=False):
        @given(allocations_data)
        def test_calculate_cpu_hours(self, users_sizes_seconds):
            """
            Test that calculate_cpu_hours returns the correct values.
            """
            cpu_hours = calculate_cpu_hours(users_sizes_seconds, sizes_data)
            # Make sure the result has the same keys as the input
            assert set(users_sizes_seconds.keys()) == set(cpu_hours.keys())
            # Make sure the calculation is correct.
            for username, sizes_seconds in users_sizes_seconds.iteritems():
                user_cpu_hours = sum(
                    [int(sizes_data[size_id]['cpu']) * size_seconds
                     for size_id, size_seconds in sizes_seconds.iteritems()]) / 3600.0
                assert user_cpu_hours == cpu_hours[username]
