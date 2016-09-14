import argparse
import json
import logging

import django
from django.utils import timezone

django.setup()

from dateutil.parser import parse

from core.models import AtmosphereUser
from core.models import UserAllocationSource
from jetstream.allocation import TASAPIDriver
from jetstream.tasks import _create_tas_report_for

USE_TAS_PROD = False

if USE_TAS_PROD:
    from atmosphere.settings.local import TACC_API_URL, TACC_API_USER, TACC_API_PASS
else:
    from atmosphere.settings.local import BETA_TACC_API_URL as TACC_API_URL, BETA_TACC_API_USER as TACC_API_USER, \
        BETA_TACC_API_PASS as TACC_API_PASS

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--end-date', help='Date to end reports', default=None)
    args = parser.parse_args()

    end_date = parse(args.end_date) if args.end_date else timezone.now()
    print 'Using end_date: %s' % end_date
    user_allocations = UserAllocationSource.objects.select_related('allocation_source', 'user').all().order_by(
        'allocation_source__name')
    try:
        print 'Going to try loading usernames from JSON...'
        with open('tacc_usernames.json', 'r') as f:
            atmo_to_tacc_usernames = json.load(f)
        print 'Loaded usernames'
    except:
        print 'Failed at loading usernames from JSON. About to get usernames from TAS API...'
        atmo_users = AtmosphereUser.objects.all()
        driver = TASAPIDriver(TACC_API_URL, TACC_API_USER, TACC_API_PASS)
        atmo_to_tacc_usernames = {user.username: driver.get_tacc_username(user) for user in atmo_users}
        with open('tacc_usernames.json', 'w') as f:
            json.dump(atmo_to_tacc_usernames, f)
        print 'Loaded usernames from TAS API'
    all_reports = []
    print 'About to create a reports'
    for user_allocation in user_allocations:
        allocation_id = user_allocation.allocation_source.source_id
        tacc_username = atmo_to_tacc_usernames[user_allocation.user.username]
        project_name = user_allocation.allocation_source.name
        print '%s - %s' % (project_name, tacc_username)
        project_report = _create_tas_report_for(
            user_allocation.user,
            tacc_username,
            project_name,
            end_date)

    print 'Number of reports created: %d' % len(all_reports)
