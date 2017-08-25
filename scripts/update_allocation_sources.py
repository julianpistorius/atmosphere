import argparse
import time
from pprint import pprint

import django

django.setup()

import core.models


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--users', required=True,
                        help='Usernames for whom to update allocation. (comma separated, with no spaces)')
    parser.add_argument('--compute-allowed', required=True, type=int,
                        help='New compute_allowed for the allocations sources')
    args = parser.parse_args()

    usernames = [username.strip() for username in args.users.split(',')]
    allocation_sources = core.models.AllocationSource.objects.filter(name__in=usernames)
    for allocation_source in allocation_sources:
        assert isinstance(allocation_source, core.models.AllocationSource)
        payload = {
            'allocation_source_name': allocation_source.name,
            'compute_allowed': args.compute_allowed
        }
        event = core.models.EventTable.create_event(
            'allocation_source_compute_allowed_changed',
            payload,
            allocation_source.name
        )
        pprint(event.payload)

    time.sleep(1)

    updated_allocation_sources = core.models.AllocationSource.objects.filter(name__in=usernames)
    for updated_allocation_source in updated_allocation_sources:
        pprint(updated_allocation_source)
        assert isinstance(updated_allocation_source, core.models.AllocationSource)
        assert updated_allocation_source.compute_allowed == args.compute_allowed


if __name__ == '__main__':
    main()
