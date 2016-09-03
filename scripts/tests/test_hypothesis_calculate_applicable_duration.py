""" Tests for the calculate_applicable_duration function """
import datetime

import pytz
from hypothesis import given, settings, strategies as st
from hypothesis.extra.datetime import datetimes
from hypothesis.extra.django import TestCase as HypothesisTestCase

from scripts.allocation_status_script import calculate_applicable_duration

ALL_TIMEZONES = list(map(pytz.timezone, pytz.all_timezones))
POSSIBLE_STATUSES = (
    'active',
    'build',
    'pending',
    'running',
    'terminated',
    'shutting-down',
    'suspended',
    'shutoff',
    'hard_reboot',
    'resize',
    'verify_resize',
    'error',
    'rescue',
    'migrating',
    'reboot',
    'deleted',
    'unknown',
    'deploying',
    'networking',
    'deploy_error',
    'Unknown',
    'paused',
    '',
    None
)


class TestAllocationStatusScriptApplicableDuration(HypothesisTestCase):
    with settings(max_examples=1000):
        @given(
            st.text(),
            datetimes(),
            datetimes(),
            datetimes(),
            datetimes()
        )
        def test_never_crash_random_strings(self, status, start_date, end_date, report_start_date, report_end_date):
            """
            Test that calculate_applicable_duration never crashes
            """
            instance_history_item = {'status': status, 'start_date': start_date, 'end_date': end_date}
            # instance_history_item = {'status': 'active', 'start_date': str(start_date), 'end_date': str(end_date)}
            duration = calculate_applicable_duration(instance_history_item, report_start_date, report_end_date)
            assert duration is not None
            assert type(duration) in (int, datetime.timedelta)
            if type(duration) == int:
                assert duration >= 0

    with settings(max_examples=1000):
        @given(
            st.sampled_from(POSSIBLE_STATUSES),
            datetimes(),
            datetimes(),
            datetimes(),
            datetimes()
        )
        def test_never_crash_valid_status(self, status, start_date, end_date, report_start_date, report_end_date):
            """
            Test that calculate_applicable_duration never crashes, given valid statuses, and that
            it always returns
            """
            instance_history_item = {'status': status, 'start_date': start_date.isoformat(),
                                     'end_date': end_date.isoformat()}
            duration = calculate_applicable_duration(instance_history_item, report_start_date, report_end_date)
            assert duration is not None
            assert type(duration) in (int, datetime.timedelta)
            if type(duration) == int:
                assert duration == 0
            if type(duration) == datetime.timedelta:
                assert duration >= datetime.timedelta(seconds=0)

    with settings(max_examples=1000):
        @given(
            st.sampled_from(('active',)),
            datetimes(min_year=2000, max_year=2002),  # instance start date
            datetimes(min_year=2005, max_year=2007),  # instance end date
            datetimes(min_year=1999, max_year=2003),  # report start date
            datetimes(min_year=2004, max_year=2008)  # report end date
        )
        def test_non_zero_cases(self, status, start_date, end_date, report_start_date, report_end_date):
            """
            Test that calculate_applicable_duration never returns 0 (or a zero timedelta) given
            dates which make sense, and a status of 'active'.
            """
            instance_history_item = {'status': status, 'start_date': start_date.isoformat(),
                                     'end_date': end_date.isoformat()}
            duration = calculate_applicable_duration(instance_history_item, report_start_date, report_end_date)
            assert duration is not None
            assert duration != 0
            assert type(duration) in (datetime.timedelta,)
            assert duration >= datetime.timedelta(seconds=0)
