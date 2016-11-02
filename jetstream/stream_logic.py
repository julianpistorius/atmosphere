import collections
import datetime
import functools
import itertools

import more_itertools

InstanceStatusHistoryItem = collections.namedtuple('InstanceStatusHistoryItem', ['instance_id',
                                                                                 'activity',
                                                                                 'size__cpu',
                                                                                 'status__name',
                                                                                 'start_date',
                                                                                 'instance__created_by__username'])
EventItem = collections.namedtuple('EventItem', ['id',
                                                 'uuid',
                                                 'entity_id',
                                                 'name',
                                                 'payload',
                                                 'timestamp'])
HeartBeat = collections.namedtuple('HeartBeat', ['timestamp'])
Instance = collections.namedtuple('Instance', ['id',
                                               'current_status',
                                               'current_activity',
                                               'current_allocation_source',
                                               'allocations_durations',
                                               'created_by',
                                               'size_cpu',
                                               'start_date',
                                               'last_updated',
                                               'event_count',
                                               'active_duration'])
User = collections.namedtuple('User', ['username',
                                       'inactive_instances',
                                       'active_instances',
                                       'allocations_usage'])
AllocationSource = collections.namedtuple('AllocationSource', ['id',
                                                               'users',
                                                               'all_usage'])
Accumulator = collections.namedtuple('Accumulator', ['instances',
                                                     'active_instance_ids',
                                                     'users',
                                                     'allocation_sources',
                                                     'statuses',
                                                     'activities',
                                                     'instances_missing'
                                                     ])


def is_instance_active(instance):
    """Returns True if the instance is active, False if not.

    :param instance: Instance
    :return:
    :rtype: bool
    """
    assert isinstance(instance, Instance)
    return instance.current_status == 'active' and not instance.current_activity


def instance_apply_status_history(instance, instance_status_history):
    assert isinstance(instance_status_history, InstanceStatusHistoryItem)
    ish = instance_status_history
    if instance:
        assert isinstance(instance, Instance)
        assert instance.id == ish.instance_id
        active_duration = instance.active_duration
        if is_instance_active(instance):
            active_duration_since_last_event = ish.start_date - instance.last_updated
            active_duration += active_duration_since_last_event
            current_allocation_source = instance.current_allocation_source
            current_allocation_source_duration = instance.allocations_durations.get(current_allocation_source,
                                                                                    datetime.timedelta())
            current_allocation_source_duration += active_duration_since_last_event * ish.size__cpu
            instance.allocations_durations[current_allocation_source] = current_allocation_source_duration
        updated_instance = instance._replace(current_status=ish.status__name,
                                             current_activity=ish.activity,
                                             size_cpu=ish.size__cpu,
                                             last_updated=ish.start_date,
                                             event_count=instance.event_count + 1,
                                             active_duration=active_duration)
    else:
        updated_instance = Instance(id=ish.instance_id,
                                    current_status=ish.status__name,
                                    current_activity=ish.activity,
                                    current_allocation_source='N/A',
                                    allocations_durations={},
                                    created_by=ish.instance__created_by__username,
                                    size_cpu=ish.size__cpu,
                                    start_date=ish.start_date,
                                    last_updated=ish.start_date,
                                    event_count=1,
                                    active_duration=datetime.timedelta())

    return updated_instance


def user_apply_instance_change(user, instance, updated_instance):
    """Update user data as a result of an instance change.

    :param user: The user data to update based on the changed instance
    :type user: User

    :param instance: Instance data before the change occurred
    :type instance: Instance

    :param updated_instance: Instance data after the change occurred
    :type updated_instance: Instance

    :return: The user, updated with things like new allocations usage
    :rtype: User
    """
    if is_instance_active(updated_instance):
        user.active_instances.add(updated_instance.id)
        user.inactive_instances.discard(updated_instance.id)
    else:
        user.active_instances.discard(updated_instance.id)
        user.inactive_instances.add(updated_instance.id)

    if instance and is_instance_active(instance):
        assert isinstance(instance, Instance)
        current_allocation_source_duration = user.allocations_usage.get(instance.current_allocation_source,
                                                                        datetime.timedelta())
        current_allocation_source_duration += instance.allocations_durations.get(
            instance.current_allocation_source,
            datetime.timedelta())
        user.allocations_usage[instance.current_allocation_source] = current_allocation_source_duration
    return user


def handle_instance_status(accumulator, item):
    try:
        instance_status_history = InstanceStatusHistoryItem(**item)
    except TypeError:
        return None
    assert isinstance(accumulator, Accumulator)

    assert isinstance(accumulator.statuses, collections.Counter)
    accumulator.statuses[instance_status_history.status__name] += 1

    assert isinstance(accumulator.activities, collections.Counter)
    accumulator.activities[instance_status_history.activity] += 1

    assert isinstance(accumulator.instances, dict)
    instance = accumulator.instances.get(instance_status_history.instance_id)  # Use a `defaultdict` here?
    updated_instance = instance_apply_status_history(instance, instance_status_history)
    accumulator.instances[instance_status_history.instance_id] = updated_instance

    assert isinstance(accumulator.active_instance_ids, set)
    if is_instance_active(updated_instance):
        accumulator.active_instance_ids.add(updated_instance.id)
    else:
        accumulator.active_instance_ids.discard(updated_instance.id)

    assert isinstance(accumulator.users, dict)
    username = instance_status_history.instance__created_by__username
    user = accumulator.users.get(username,
                                 User(username=username,
                                      inactive_instances=set(),
                                      active_instances=set(),
                                      allocations_usage={}))

    updated_user = user_apply_instance_change(user, instance, updated_instance)
    accumulator.users[username] = updated_user

    return accumulator


def instance_apply_heartbeat(instance, heartbeat):
    assert isinstance(heartbeat, HeartBeat)
    assert isinstance(instance, Instance)
    if is_instance_active(instance) and heartbeat.timestamp > instance.last_updated:
        active_duration = instance.active_duration
        active_duration_since_last_event = (heartbeat.timestamp - instance.last_updated) * instance.size_cpu
        active_duration += active_duration_since_last_event
        current_allocation_source = instance.current_allocation_source
        current_allocation_source_duration = instance.allocations_durations.get(current_allocation_source,
                                                                                datetime.timedelta())
        current_allocation_source_duration += active_duration_since_last_event
        instance.allocations_durations[current_allocation_source] = current_allocation_source_duration
        updated_instance = instance._replace(last_updated=heartbeat.timestamp,
                                             event_count=instance.event_count + 1,
                                             active_duration=active_duration)

        return updated_instance
    else:
        return instance


def handle_heartbeat(accumulator, item):
    try:
        heartbeat = HeartBeat(**item)
    except TypeError:
        return None
    assert isinstance(accumulator, Accumulator)
    assert isinstance(accumulator.instances, dict)
    assert isinstance(accumulator.active_instance_ids, set)

    for instance_id in accumulator.active_instance_ids:
        instance = accumulator.instances[instance_id]
        updated_instance = instance_apply_heartbeat(instance, heartbeat)
        accumulator.instances[instance_id] = updated_instance

    return accumulator


def instance_apply_event(instance, event):
    assert isinstance(event, EventItem)
    assert isinstance(instance, Instance)
    if event.payload['instance_id'] != instance.id:
        raise ValueError('event instance_id does not match instance: {} > {}'.format(event.payload['instance_id'],
                                                                                     instance.id))
    if event.timestamp < instance.last_updated:
        raise ValueError('instance is newer than the event: {} > {}'.format(instance, event))
    if event.name != 'instance_allocation_source_changed':
        raise ValueError('Unknown event: {}'.format(event))

    new_allocation_source = event.payload['allocation_source_id']
    active_duration = instance.active_duration
    current_allocation_source = instance.current_allocation_source
    if new_allocation_source == current_allocation_source:
        raise ValueError('new_allocation_source_id == current_allocation_source')
    if is_instance_active(instance):
        active_duration_since_last_event = event.timestamp - instance.last_updated
        current_allocation_source_duration = instance.allocations_durations.get(current_allocation_source,
                                                                                datetime.timedelta())
        current_allocation_source_duration += active_duration_since_last_event
        instance.allocations_durations[current_allocation_source] = current_allocation_source_duration
        active_duration += active_duration_since_last_event

    updated_instance = instance._replace(last_updated=event.timestamp,
                                         current_allocation_source=new_allocation_source,
                                         event_count=instance.event_count + 1,
                                         active_duration=active_duration)

    return updated_instance


def handle_event(accumulator, item):
    """Something. Figure out.

    :rtype: object
    :param accumulator:
    :param item:
    :return: Either None or some object
    """
    try:
        event_item = EventItem(**item)
    except TypeError:
        return None
    assert isinstance(accumulator, Accumulator)
    assert isinstance(accumulator.instances, dict)

    # print event_item.name, event_item.entity_id, event_item.payload
    if event_item.name == 'instance_allocation_source_changed':
        instance_id = event_item.payload['instance_id']
        try:
            instance = accumulator.instances[instance_id]
            updated_instance = instance_apply_event(instance, event_item)
            accumulator.instances[instance_id] = updated_instance
        except KeyError:
            # print('Can\'t find instance for the event: {}'.format(event_item))
            accumulator.instances_missing[instance_id] += 1
            # raise
    return accumulator


def update_state(current_state, generic_event):
    """Generate the next state from the current state and an event.

    :param current_state: The current state of the system
    :type current_state: Accumulator
    :param generic_event: And event which can modify the state
    :type generic_event: Any
    :return: The next state
    :rtype: Accumulator
    """
    new_state = (handle_instance_status(current_state, generic_event) or
                 handle_event(current_state, generic_event) or
                 handle_heartbeat(current_state, generic_event))
    if not new_state:
        raise ValueError('Unknown item: {}'.format(generic_event))
    assert isinstance(new_state, Accumulator)
    return new_state


def key_function(item):
    """Returns the applicable timestamp or datetime for a generic event.

    :rtype: datetime.datetime
    :param collections.Mapping item: A generic event with either a 'timestamp' or 'start_date' entry
    :return: A date time which indicates when the event happened
    """
    return item.get('timestamp', None) or item['start_date']


def batch_calculate_system_state(end_date):
    """Calculate the state of the system as a batch from the beginning of time - up to an end date.

    :param end_date: The date up to which to calculate the system date
    :type end_date: datetime.datetime
    :return: The state of the system as calculated up to a certain date
    :rtype: Accumulator
    """
    from core import models
    events_queryset = models.EventTable.objects.filter(timestamp__lte=end_date).filter(
        name='instance_allocation_source_changed'
    ).values().order_by('timestamp')

    instance_status_histories_queryset = models.InstanceStatusHistory.objects.filter(
        start_date__lte=end_date
    ).values('instance_id',
             'activity',
             'size__cpu',
             'status__name',
             'start_date',
             'instance__created_by__username').order_by('start_date')

    heart_beat = [{'timestamp': end_date}]
    event_stream = more_itertools.collate(events_queryset, instance_status_histories_queryset, key=key_function)
    event_stream = itertools.chain(event_stream, heart_beat)

    initial_state = Accumulator(instances={},
                                active_instance_ids=set(),
                                users={},
                                allocation_sources={},
                                statuses=collections.Counter(),
                                activities=collections.Counter(),
                                instances_missing=collections.Counter()
                                )
    final_state = functools.reduce(update_state, event_stream, initial_state)
    assert isinstance(final_state, Accumulator)
    return final_state


__all__ = [batch_calculate_system_state, Accumulator]
