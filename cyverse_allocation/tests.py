import pprint
import uuid

from django.conf import settings
from django.core import exceptions
from django.test import TestCase

from api.tests.factories import UserFactory
from core.models import AllocationSource
from core.models import EventTable
from core.models import UserAllocationSource


class CyVerseAllocationTests(TestCase):
    def setUp(self):
        if 'cyverse_allocation' not in settings.INSTALLED_APPS:
            self.skipTest('CyVerse Allocation plugin is not enabled')

    def test_allocation_source_created(self):
        new_allocation_source = {
            'source_id': str(uuid.uuid4()),
            'name': 'TestAllocationSourceCreateScenario',
            'compute_allowed': 50000
        }

        # Make sure no allocation_source_created event for this source exists
        event_count_before = EventTable.objects.filter(
            name='allocation_source_created',
            payload__name='TestAllocationSourceCreateScenario'
        ).count()
        self.assertEqual(event_count_before, 0)

        # Make sure that no Allocation Source with our test source name exists
        allocation_source_count_before = AllocationSource.objects.filter(
            name=new_allocation_source['name']).count()
        self.assertEqual(allocation_source_count_before, 0)

        allocation_source_count_before = AllocationSource.objects.filter(
            source_id=new_allocation_source['source_id']).count()
        self.assertEqual(allocation_source_count_before, 0)

        # Add an event 'allocation_source_created' with our test source name
        new_event = EventTable.create_event(name='allocation_source_created',
                                            payload=new_allocation_source,
                                            entity_id=new_allocation_source['source_id'])

        # Make sure we added the event successfully
        event_count_after = EventTable.objects.filter(
            name='allocation_source_created',
            payload__name='TestAllocationSourceCreateScenario'
        ).count()
        self.assertEqual(event_count_after, 1)

        # Make sure that there is now an Allocation Source with the test name
        allocation_source_count_after = AllocationSource.objects.filter(
            source_id=new_allocation_source['source_id'],
            name=new_allocation_source['name']).count()
        self.assertEqual(allocation_source_count_after, 1)

        allocation_source = AllocationSource.objects.filter(
            source_id=new_allocation_source['source_id'],
            name=new_allocation_source['name']).first()
        self.assertEqual(allocation_source.compute_allowed, new_allocation_source['compute_allowed'])

    def test_user_allocation_source_assigned(self):
        new_allocation_source = {
            'source_id': str(uuid.uuid4()),
            'name': 'TestAllocationSourceAssociateScenario',
            'compute_allowed': 50000
        }
        new_event = EventTable.create_event(name='allocation_source_created',
                                            payload=new_allocation_source,
                                            entity_id=new_allocation_source['source_id'])
        user = UserFactory.create()
        new_user_allocation_source = {
            'source_id': new_allocation_source['source_id'],
            'username': user.username
        }

        # Make sure no allocation_source_assigned event for this user and source exists
        event_count_before = EventTable.objects.filter(
            name='user_allocation_source_assigned',
            payload__username=user.username,
            payload__source_id=new_user_allocation_source['source_id']
        ).count()
        self.assertEqual(event_count_before, 0)

        # Make sure that no Allocation Source and User combination exists
        user_allocation_source_count_before = UserAllocationSource.objects.filter(
            allocation_source__source_id=new_user_allocation_source['source_id'],
            user=user).count()
        self.assertEqual(user_allocation_source_count_before, 0)

        # Add an event 'allocation_source_created' with our test source name
        new_event = EventTable.create_event(name='user_allocation_source_assigned',
                                            payload=new_user_allocation_source,
                                            entity_id=new_user_allocation_source['username'])

        # Make sure we added the event successfully
        event_count_after = EventTable.objects.filter(
            name='user_allocation_source_assigned',
            payload__username=user.username,
            payload__source_id=new_user_allocation_source['source_id']
        ).count()
        self.assertEqual(event_count_after, 1)

        # Make sure that there is now an Allocation Source with the test name
        user_allocation_source_count_after = UserAllocationSource.objects.filter(
            allocation_source__source_id=new_user_allocation_source['source_id'],
            user=user).count()
        self.assertEqual(user_allocation_source_count_after, 1)

        user_allocation_source = UserAllocationSource.objects.filter(
            allocation_source__source_id=new_user_allocation_source['source_id'],
            user=user).first()
        self.assertEqual(user_allocation_source.allocation_source.compute_allowed,
                         new_allocation_source['compute_allowed'])
        self.assertEqual(user_allocation_source.allocation_source.source_id, new_allocation_source['source_id'])
        self.assertEqual(user_allocation_source.allocation_source.name, new_allocation_source['name'])

    def test_instance_allocation_source_changed_validators(self):
        # Valid:
        # {'instance_id': 'bb0d193a-3da4-413a-b91d-1f054fba7af6', 'allocation_source_id': '27475'}
        # Invalid:
        # '64436cbb-ce43-45b4-b9a2-2086575d2cf2'
        # {'username': 'iparask', 'instance_id': '64436cbb-ce43-45b4-b9a2-2086575d2cf2', 'allocation_source_id': '39262'}

        new_allocation_source = {
            'source_id': str(uuid.uuid4()),
            'name': 'TestAllocationSourceCreateScenario',
            'compute_allowed': 50000
        }
        EventTable.create_event(name='allocation_source_created',
                                payload=new_allocation_source,
                                entity_id=new_allocation_source['source_id'])
        user = UserFactory.create()
        new_user_allocation_source = {
            'source_id': new_allocation_source['source_id'],
            'username': user.username
        }
        # Add an event 'allocation_source_created' with our test source name
        EventTable.create_event(name='user_allocation_source_assigned',
                                payload=new_user_allocation_source,
                                entity_id=new_user_allocation_source['username'])

        valid_instance_allocation_changed_payload = {
            'instance_id': 'bb0d193a-3da4-413a-b91d-1f054fba7af6',
            'allocation_source_id': new_allocation_source['source_id']
        }

        valid_event = EventTable.create_event(name='instance_allocation_source_changed',
                                              payload=valid_instance_allocation_changed_payload,
                                              entity_id=new_user_allocation_source['username'])
        pprint.pprint(valid_event)

        invalid_instance_allocation_changed_payload = {
            'username': new_user_allocation_source['username'],
            'instance_id': 'bb0d193a-3da4-413a-b91d-1f054fba7af6',
            'allocation_source_id': new_allocation_source['source_id']
        }
        with self.assertRaises(exceptions.ValidationError) as validation_error:
            EventTable.create_event(name='instance_allocation_source_changed',
                                    payload=invalid_instance_allocation_changed_payload,
                                    entity_id='bb0d193a-3da4-413a-b91d-1f054fba7af6')

        self.assertEqual(validation_error.exception.code, 'event_schema')
        # noinspection SpellCheckingInspection
        self.assertEqual(validation_error.exception.message, 'Event serializer keys do not match payload keys')
