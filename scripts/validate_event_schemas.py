"""
To run using `parallel`:

```bash
export PYTHONPATH="$PWD:$PYTHONPATH"
export DJANGO_SETTINGS_MODULE='atmosphere.settings'
parallel --pipepart -a ~/Documents/variables/atmo_prod_jetstream_public_event_table.csv \
  python scripts/validate_event_schemas.py
```
"""

import collections
import csv
import fileinput
import json

import django

django.setup()

MockEvent = collections.namedtuple('MockEvent', ['name', 'payload'])


def validate_event_schemas(events):
    from core.hooks.allocation_source import validate_event_schema
    exception_messages_counter = collections.Counter()
    for event in events:
        event_name = event['name']
        event_payload = json.loads(event['payload'])
        mock_event = MockEvent(name=event_name, payload=event_payload)
        try:
            validate_event_schema(mock_event)
        except Exception as e:
            # pprint.pprint(e)
            params = getattr(e, 'params', {})
            show_value = params.get('show_value')
            annotated_message = '{} - {} - {}'.format(e.message, event_name, show_value)
            messages = [annotated_message]
            exception_messages_counter.update(messages)
    return exception_messages_counter


if __name__ == '__main__':
    # import pydevd
    # pydevd.settrace('127.0.0.1', port=4567, stdoutToServer=True, stderrToServer=True, suspend=False)

    csv_reader = csv.DictReader(f=fileinput.input(),
                                fieldnames=('id', 'uuid', 'entity_id', 'name', 'payload', 'timestamp'))
    events = csv_reader
    unique_exception_messages = validate_event_schemas(events)
    for message, count in unique_exception_messages.iteritems():
        print(message, count)
    print('unique_exception_messages: {}'.format(len(unique_exception_messages)))
