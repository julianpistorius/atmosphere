import collections
import decimal
import itertools
import pprint
import more_itertools

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils import timezone
from threepio import logger
from uuid import uuid4

class AllocationSource(models.Model):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    compute_allowed = models.IntegerField()
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    renewal_strategy = models.CharField(max_length=255, default="default")

    @classmethod
    def for_user(cls, user):
        source_ids = UserAllocationSource.objects.filter(user=user).values_list('allocation_source', flat=True)
        return AllocationSource.objects.filter(id__in=source_ids)

    def get_instance_ids(self):
        return self.instanceallocationsourcesnapshot_set.all().values_list('instance__provider_alias', flat=True)

    def is_over_allocation(self, user=None):
        """Return whether the allocation source `compute_used` is over the `compute_allowed`.

        :return: bool
        :rtype: bool
        """
        return self.time_remaining(user) < 0

    def time_remaining(self, user=None):
        """
        Returns the remaining compute_allowed,

        user: If passed in *and* allocation source is 'special', calculate remaining time based on user snapshots.

        Will return a negative number if 'over allocation', when `compute_used` is larger than `compute_allowed`.
        Will return Infinity if `compute_allowed` is `-1` (or any negative number)
        :return: decimal.Decimal
        :rtype: decimal.Decimal
        """
        # Handling the 'SPECIAL_ALLOCATION_SOURCES'
        time_shared_allocations = getattr(settings, 'SPECIAL_ALLOCATION_SOURCES', {})
        if user and self.name in time_shared_allocations.keys():
            try:
                compute_allowed = time_shared_allocations[self.name]['compute_allowed']
            except:
                raise Exception(
                    "The structure of settings.SPECIAL_ALLOCATION_SOURCES "
                    "has changed! Verify your settings are correct and/or "
                    "change the lines of code above.")
            try:
                last_snapshot = self.user_allocation_snapshots.get(user=user)
            except ObjectDoesNotExist:
                logger.exception('User allocation snapshot does not exist anymore (or yet), so returning -1')
                return -1
        else:
            compute_allowed = self.compute_allowed
            last_snapshot = self.snapshot
        if compute_allowed < 0:
            return decimal.Decimal('Infinity')
        compute_used = last_snapshot.compute_used if last_snapshot else 0
        remaining_compute = compute_allowed - compute_used
        return remaining_compute


    @property
    def compute_used_updated(self):
        """
        Using the AllocationSourceSnapshot table, return updated
        """
        if not self.snapshot:
            return -1
        return self.snapshot.updated

    @property
    def compute_used(self):
        """
        Using the AllocationSourceSnapshot table, return compute_used
        """
        if not self.snapshot:
            return -1
        return self.snapshot.compute_used

    @property
    def all_users(self):
        """
        Using the UserAllocationSource join-table, return a list of all (known) users.
        """
        from core.models import AtmosphereUser
        user_ids = self.users.values_list('user', flat=True)
        user_qry = AtmosphereUser.objects.filter(id__in=user_ids)
        return user_qry

    def __unicode__(self):
        return "%s (ID:%s, Compute Allowed:%s)" %\
            (self.name, self.uuid,
             self.compute_allowed)


    class Meta:
        db_table = 'allocation_source'
        app_label = 'core'

class UserAllocationSource(models.Model):
    """
    This table keeps track of whih allocation sources belong to an AtmosphereUser.

    NOTE: This table is basically a cache so that we do not have to query out to the
    "Allocation Source X" API endpoint each call.
          It is presumed that this table will be *MAINTAINED* regularly via periodic task.
    """

    user = models.ForeignKey("AtmosphereUser", related_name="user_allocation_sources")
    # FIXME: this will not return a QuerySet of AtmosphereUser, it will return a QuerySet of UserAllocationSource.. (Rename related_name?)
    allocation_source = models.ForeignKey(AllocationSource, related_name="users")

    def __unicode__(self):
        return "%s (User:%s, AllocationSource:%s)" %\
            (self.id, self.user,
             self.allocation_source)

    class Meta:
        db_table = 'user_allocation_source'
        app_label = 'core'
        unique_together = ('user', 'allocation_source')


class UserAllocationSnapshot(models.Model):
    """
    Fixme: Potential optimization -- user_allocation_source could just store burn_rate and updated?
    """
    user = models.ForeignKey("AtmosphereUser", related_name="user_allocation_snapshots")
    allocation_source = models.ForeignKey(AllocationSource, related_name="user_allocation_snapshots")
    # all fields are stored in DecimalField to allow for partial hour calculation
    compute_used = models.DecimalField(max_digits=19, decimal_places=3)
    burn_rate = models.DecimalField(max_digits=19, decimal_places=3)
    updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return "User %s + AllocationSource %s: Total AU Usage:%s Burn Rate:%s hours/hour Updated:%s" %\
            (self.user, self.allocation_source, self.compute_used, self.burn_rate, self.updated)

    class Meta:
        db_table = 'user_allocation_snapshot'
        app_label = 'core'
        unique_together = ('user','allocation_source')


class InstanceAllocationSourceSnapshot(models.Model):
    instance = models.OneToOneField("Instance")
    allocation_source = models.ForeignKey(AllocationSource)
    updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return "%s is using allocation %s" %\
            (self.instance, self.allocation_source)
    class Meta:
        db_table = 'instance_allocation_source_snapshot'
        app_label = 'core'


class AllocationSourceSnapshot(models.Model):
    allocation_source = models.OneToOneField(AllocationSource, related_name="snapshot")
    updated = models.DateTimeField(auto_now=True)
    last_renewed = models.DateTimeField(default=timezone.now)
    # all fields are stored in DecimalField to allow for partial hour calculation
    global_burn_rate = models.DecimalField(max_digits=19, decimal_places=3)
    compute_used = models.DecimalField(max_digits=19, decimal_places=3)
    compute_allowed = models.DecimalField(max_digits=19, decimal_places=3, default=0)

    def __unicode__(self):
        return "%s (Used:%s, Burn Rate:%s Updated on:%s)" %\
            (self.allocation_source, self.compute_used,
             self.global_burn_rate, self.updated)
    class Meta:
        db_table = 'allocation_source_snapshot'
        app_label = 'core'


def total_usage(username, start_date, allocation_source_name=None, end_date=None, burn_rate=False, email=None,
                fast=False):
    fast_result = total_usage_fast(username, start_date, allocation_source_name, end_date, burn_rate)
    slow_result = total_usage_slow(username, start_date, allocation_source_name, end_date, burn_rate, email)
    logger.debug('fast_result: %s:', fast_result)
    logger.debug('slow_result: %s:', slow_result)
    if fast_result != slow_result:
        logger.error('fast_result != slow_result: %s != %s', fast_result, slow_result)

    if fast:
        return fast_result
    else:
        return slow_result


def total_usage_slow(username, start_date, allocation_source_name=None, end_date=None, burn_rate=False, email=None):
    """
        This function outputs the total allocation usage in hours
    """
    from service.allocation_logic import create_report
    if not end_date:
        end_date = timezone.now()
    user_allocation = create_report(start_date,end_date,user_id=username,allocation_source_name=allocation_source_name)
    if email:
        return user_allocation
    total_allocation = 0.0
    for data in user_allocation:
        #print data['instance_id'], data['allocation_source'], data['instance_status_start_date'], data['instance_status_end_date'], data['applicable_duration']
        if not data['allocation_source']=='N/A':
            total_allocation += data['applicable_duration']
    compute_used_total = round(total_allocation/3600.0,2)
    if compute_used_total > 0:
        logger.info("Total usage for User %s with AllocationSource %s from %s-%s = %s"
                    % (username, allocation_source_name, start_date, end_date, compute_used_total))
    if burn_rate:
        burn_rate_total = 0 if len(user_allocation)<1 else user_allocation[-1]['burn_rate']
        if burn_rate_total != 0:
            logger.info("User %s with AllocationSource %s Burn Rate: %s"
                        % (username, allocation_source_name, burn_rate_total))
        return [compute_used_total, burn_rate_total]
    return compute_used_total


def get_allocation_source_object(source_id):
    if not source_id:
        raise Exception('No source_id provided in _get_allocation_source_object method')

    return AllocationSource.objects.filter(uuid=source_id).last()


##############################################
# New code

InstanceStatusHistoryItem = collections.namedtuple('InstanceStatusHistoryItem',
                                                   ['instance_id', 'instance__provider_alias', 'activity', 'size__cpu',
                                                    'instance__created_by__username', 'status__name', 'start_date'])
EventItem = collections.namedtuple('EventItem', ['id', 'uuid', 'entity_id', 'name', 'payload', 'timestamp'])
TickEventItem = collections.namedtuple('TickEventItem', ['timestamp'])


def instance_state_factory():
    default_instance_statue = {
        'times_seen': 0,
        'allocation_source': 'N/A',
        'status': ''
    }
    return default_instance_statue


# INSTANCE_STATE_DEFAULT = collections.defaultdict(instance_state_factory)
USER_INSTANCES_INITIAL_STATE = {
}


def calculate_usage(accum_value, item):
    # print('accum_value: {}'.format(pprint.pformat(accum_value)))
    logger.debug('calculate_usage - accum_value: %s', pprint.pformat(accum_value))
    # print('item: {}'.format(pprint.pformat(item)))
    logger.debug('calculate_usage - item: %s', pprint.pformat(item))
    # accum_value[type(item)] = accum_value[type(item)] + 1
    if isinstance(item, InstanceStatusHistoryItem):
        item_id = item.instance_id
        instance_state = accum_value[item_id]
    elif isinstance(item, EventItem):
        # TODO: Sometimes it will be in the `entity_id` field.
        item_id = item.payload['instance_id']
        instance_state = accum_value[item_id]

    else:
        raise ValueError('Unknown event item: {}'.format(item))
    instance_state['times_seen'] += 1
    accum_value[item_id] = instance_state
    return accum_value


def get_new_instance(start_date):
    instance = {
        'username': None,
        'first_event_date': start_date,
        'last_event_date': start_date,
        'total_active_cpu_seconds': 0,
        'allocation_active_cpu_seconds': {'no_allocation': 0},
        'activity': 'unknown',
        'status': 'unknown',
        'cpus': 0,
        'is_active': False,
        'allocation_source': None
    }
    return instance


def apply_instance_status_history(user_instances, instance_status_history):
    assert isinstance(instance_status_history, InstanceStatusHistoryItem)
    instance_provider_alias = instance_status_history.instance__provider_alias
    instance = user_instances.get(instance_provider_alias, get_new_instance(instance_status_history.start_date))
    if not instance['username']:
        instance['username'] = instance_status_history.instance__created_by__username

    was_active = instance['is_active']
    if was_active:
        # Add up the run time since the last event, multiplied by the CPUs
        time_since_last_event = instance_status_history.start_date - instance['last_event_date']
        cpus = instance['cpus']
        cpu_seconds = time_since_last_event * cpus
        instance['total_active_cpu_seconds'] += cpu_seconds
        active_allocation = instance['allocation_source'] or 'no_allocation'
        allocation_cpu_seconds = instance['allocation_active_cpu_seconds'].get(active_allocation, 0)
        new_allocation_cpu_seconds = allocation_cpu_seconds + cpu_seconds
        instance['allocation_active_cpu_seconds'][active_allocation] = new_allocation_cpu_seconds

    is_now_active = not instance_status_history.status__name and not instance_status_history.activity

    instance['activity'] = instance_status_history.activity
    instance['status'] = instance_status_history.status__name
    instance['cpus'] = instance_status_history.size__cpu
    instance['is_active'] = is_now_active
    instance['last_event_date'] = instance_status_history.start_date
    user_instances[instance_provider_alias] = instance
    return user_instances


def apply_clear_event(user_instances, event):
    # Clear all the CPU seconds before the event
    # TODO: And/or make a checkpoint event that copies the content as it is to a timestamped index
    # Can then do a sum for reports & such.
    pass

def apply_tick_event(user_instances, event):
    assert isinstance(event, TickEventItem)
    for instance_provider_alias, instance in user_instances.items():
        was_active = instance['is_active']
        if was_active:
            # Add up the run time since the last event, multiplied by the CPUs
            time_since_last_event = event.timestamp - instance['last_event_date']
            cpus = instance['cpus']
            cpu_seconds = time_since_last_event * cpus
            instance['total_active_cpu_seconds'] += cpu_seconds
            active_allocation = instance['allocation_source'] or 'no_allocation'
            allocation_cpu_seconds = instance['allocation_active_cpu_seconds'].get(active_allocation, 0)
            updated_allocation_cpu_seconds = allocation_cpu_seconds + cpu_seconds
            instance['allocation_active_cpu_seconds'][active_allocation] = updated_allocation_cpu_seconds
        instance['last_event_date'] = event.timestamp
        user_instances[instance_provider_alias] = instance
    return user_instances


def apply_instance_event(user_instances, event):
    assert isinstance(event, EventItem)
    # TODO: Sometimes it will be in the `entity_id` field.
    instance_provider_alias = event.payload['instance_id']
    instance = user_instances.get(instance_provider_alias, get_new_instance(event.timestamp))

    was_active = instance['is_active']
    if was_active:
        # Add up the run time since the last event, multiplied by the CPUs
        time_since_last_event = event.timestamp - instance['last_event_date']
        cpus = instance['cpus']
        cpu_seconds = time_since_last_event * cpus
        instance['total_active_cpu_seconds'] += cpu_seconds
        active_allocation = instance['allocation_source'] or 'no_allocation'
        allocation_cpu_seconds = instance['allocation_active_cpu_seconds'].get(active_allocation, 0)
        updated_allocation_cpu_seconds = allocation_cpu_seconds + cpu_seconds
        instance['allocation_active_cpu_seconds'][active_allocation] = updated_allocation_cpu_seconds

    if 'allocation_source_name' in event.payload:
        new_allocation_source = event.payload['allocation_source_name']
        instance['allocation_source'] = new_allocation_source
        no_allocation_cpu_seconds = instance['allocation_active_cpu_seconds']['no_allocation']
        if no_allocation_cpu_seconds > 0:
            new_allocation_cpu_seconds = instance['allocation_active_cpu_seconds'].get(new_allocation_source, 0)
            new_allocation_cpu_seconds += no_allocation_cpu_seconds
            instance['allocation_active_cpu_seconds'][new_allocation_source] = new_allocation_cpu_seconds
            instance['allocation_active_cpu_seconds']['no_allocation'] = 0

    instance['last_event_date'] = event.timestamp
    user_instances[instance_provider_alias] = instance
    return user_instances


def apply_user_instances_event(user_instances, event):
    logger.debug('calculate_usage - user_instances: %s', pprint.pformat(user_instances))
    logger.debug('calculate_usage - event: %s', pprint.pformat(event))
    if isinstance(event, InstanceStatusHistoryItem):
        return apply_instance_status_history(user_instances, event)
    elif isinstance(event, EventItem):
        return apply_instance_event(user_instances, event)
    elif isinstance(event, TickEventItem):
        return apply_tick_event(user_instances, event)
    else:
        raise ValueError('Unknown event: {}'.format(event))


def instantiate_object_from_dict(class_object):
    def constructor(item):
        return class_object(**item)

    return constructor


def total_usage_fast(username, start_date=None, allocation_source_name=None, end_date=None, burn_rate=False):
    """This function outputs the total allocation usage in hours

    TODO:
     - Use N/A as the default allocation source
     - Create separate default dicts with keys of username, instance_id, and allocation_source
     - Calculate total_allocation
     - Create a function to `map` over the collated iterator - DONE
     - Use namedtuples for the stream items
    """
    from core import models
    if not end_date:
        end_date = timezone.now()

    total_allocation = 0.0
    burn_rate_total = 0
    total_items = 0

    # def default_factory():
    #     return 0
    #
    # allocation_counter = collections.defaultdict(default_factory)

    events_queryset = models.EventTable.objects.filter(timestamp__lte=end_date).filter(
        name='instance_allocation_source_changed'
    )
    if username:
        events_queryset = events_queryset.filter(
            Q(entity_id__exact=username) | Q(payload__contains={'username': username}))
    events_queryset = events_queryset.values().order_by('timestamp')

    events = itertools.imap(instantiate_object_from_dict(EventItem), events_queryset)

    instance_status_histories_queryset = models.InstanceStatusHistory.objects.filter(start_date__lte=end_date)
    if username:
        instance_status_histories_queryset = instance_status_histories_queryset.filter(
            instance__created_by__username=username
        )

    instance_status_histories_queryset = instance_status_histories_queryset.values(
        'instance_id',
        'instance__provider_alias',
        'activity', 'size__cpu',
        'status__name', 'start_date',
        'instance__created_by__username').order_by('start_date')

    pprint.pprint(instance_status_histories_queryset.query.values_select)
    instance_status_histories = itertools.imap(instantiate_object_from_dict(InstanceStatusHistoryItem),
                                               instance_status_histories_queryset)

    # for ish in instance_status_histories:
    #     pprint.pprint(ish)
    # raise NotImplementedError

    def key_function(item):
        return getattr(item, 'timestamp', None) or getattr(item, 'start_date')

    # previous_item_key = None

    # for item in more_itertools.collate(events, instance_status_histories, key=key_function):
    #     # pprint(item)
    #     total_items += 1
    #     item_key = key_function(item)
    #     if previous_item_key and previous_item_key > item_key:
    #         raise ValueError('Items are not in the correct order')
    #     previous_item_key = item_key

    if start_date:
        # Create a 'snapshot' or 'checkpoint' event
        pass

    event_stream = more_itertools.collate(events, instance_status_histories, key=key_function)
    event_stream = itertools.chain(event_stream, [TickEventItem(timestamp=end_date)])
    # result = reduce(calculate_usage, event_stream, INSTANCE_STATE_DEFAULT)
    # logger.debug('result: %s', result)

    user_instances = reduce(apply_user_instances_event, event_stream, USER_INSTANCES_INITIAL_STATE)
    logger.debug('user_instances: %s', user_instances)

    logger.debug('total_items: {}'.format(total_items))
    compute_used_total = round(total_allocation / 3600.0, 2)
    logger.debug('compute_used_total: {}'.format(compute_used_total))

    if burn_rate:
        return [compute_used_total, burn_rate_total]
    return compute_used_total
