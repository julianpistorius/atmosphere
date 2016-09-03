import csv
import logging
import os
import sys
from datetime import datetime

import records
from dateutil.parser import parse

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def write_instance_history_file(db_connection_string, report_start_date, report_end_date, status_history_filename,
                                username=None):
    required_query = '''
SELECT
  ih.instance_id,
  ih.id      AS ih_id,
  ih.start_date,
  ih.end_date,
  istat.name AS status,
  ih.activity,
  au.username,
  ih.size_id,
  s.cpu,
  s.mem,
  s.disk
FROM INSTANCE i
  LEFT JOIN instance_status_history ih
    ON i.id = ih.instance_id
  LEFT JOIN instance_status istat
    ON ih.status_id = istat.id
  LEFT JOIN atmosphere_user au
    ON i.created_by_id = au.id
  LEFT JOIN size s
    ON ih.size_id = s.id
WHERE :report_start_date <= i.start_date
      AND i.start_date <= :report_end_date
      OR :report_start_date <= i.end_date
         AND i.end_date <= :report_end_date
      OR i.start_date <= :report_start_date
         AND (
           i.end_date IS NULL
           OR :report_end_date <= i.end_date)
ORDER BY au.username,
  ih.instance_id,
  ih.id'''
    db = records.Database(db_connection_string)
    rows = db.query(required_query, report_start_date=report_start_date, report_end_date=report_end_date)
    output = rows.export('csv')
    if username:
        filter_by_username(username, output, report_start_date, report_end_date)
    with open(status_history_filename, 'w') as f:
        f.write(output)


def filter_by_username(uname, output, report_start_date, report_end_date):
    filtered_output = []

    output = output.split('\n')

    # indexes of col
    username = 6
    start_date = 2
    end_date = 3

    for rows in output:
        if rows:
            col = rows.split(',')
            if col[username] == uname and not parse(col[start_date]) > report_end_date:
                if col[end_date]:
                    if parse(col[end_date]) < report_start_date:
                        continue

                filtered_output.append(rows)

    if filtered_output:
        with open('%s_filtered_status_history.csv' % (uname), 'w') as csvfile:
            csvfile.write(
                'instance_id,instance_history_id,start_date,end_date,status,activity,username,size,cpu,mem,disk\n')
            for i in filtered_output:
                csvfile.write(i)
                csvfile.write('\n')


def calculate_user_allocation_usage(status_history_file_object, report_start_date, report_end_date):
    allocation_usage = {}
    sizes = {}
    user_instance_history_data = {}
    reader = csv.DictReader(status_history_file_object)
    current_user = ''

    for row in reader:
        if row['instance_id'] == 'instance_id' and row['disk'] == 'disk':
            # This is the first row, and it has the CSV fieldnames, so skip it. Added because of StringIO + CSV don't
            # play nice.
            continue
        if not row['username'] == current_user:
            current_user = row['username']
            # TODO: Don't reset if there is already a 'current_user' entry.
            user_instance_history_data[current_user] = []

        user_instance_history_data[current_user].append(row)

        if row['status'] != 'active':
            continue

        # Dictionary w/ usage and sizes creation
        allocations_used = calculate_applicable_duration(row, report_start_date, report_end_date)
        if not allocations_used:
            continue
        user_allocation = allocation_usage.get(row['username'], {})
        user_allocation_size_used = user_allocation.get(row['size_id'], 0)
        user_allocation_size_used = user_allocation_size_used + allocations_used.total_seconds()
        user_allocation[row['size_id']] = user_allocation_size_used
        allocation_usage[row['username']] = user_allocation

        # Size ID lookup dictionary creation
        if not row['size_id'] in sizes:
            sizes[row['size_id']] = {'cpu': row['cpu'], 'mem': row['mem'], 'disk': row['disk']}

    return allocation_usage, user_instance_history_data, sizes


def write_sizes_file(sizes, sizes_filename):
    with open(sizes_filename, 'w') as sizes_csv_file:
        sizes_writer = csv.DictWriter(sizes_csv_file, fieldnames=['size_id', 'cpu', 'mem', 'disk'])
        sizes_writer.writeheader()
        for size_id, size_details in sizes.iteritems():
            cpu, mem, disk = size_details['cpu'], size_details['mem'], size_details['disk']
            sizes_writer.writerow({'size_id': size_id, 'cpu': cpu, 'mem': mem, 'disk': disk})


def calculate_cpu_hours(allocations, sizes):
    cpu_hours = {}
    for user, usage in allocations.iteritems():
        total_time = 0
        for size, time in usage.iteritems():
            total_time += int(sizes[size]['cpu']) * time
        cpu_hours[user] = total_time / 3600.0
    return cpu_hours


def write_allocation_usage_file(allocation_usage, user_cpu_hours, allocation_usage_filename):
    with open(allocation_usage_filename, 'w') as csv_file:
        fieldnames = ['user_name', 'cpu_hours', 'allocations_used']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for user_name, allocations_used in allocation_usage.iteritems():
            writer.writerow({'user_name': user_name, 'cpu_hours': '%0.2f' % user_cpu_hours[user_name],
                             'allocations_used': allocations_used})


def write_detailed_report_file(instance_history, report_start_date, report_end_date, detailed_report_filename):
    with open(detailed_report_filename, 'w') as csv_file:
        fieldnames = ['Username', 'Instance_ID', 'Instance_Status_History_ID', 'CPU', 'Memory', 'Disk',
                      'Instance_Status_Start_Date', 'Instance_Status_End_Date', 'Report_Start_Date', 'Report_End_Date',
                      'Instance_Status', 'Duration (hours)', 'Applicable_Duration (hours)']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for user_name, user_instance_history in instance_history.iteritems():
            for history_item in user_instance_history:
                applicable_duration = calculate_applicable_duration(history_item, report_start_date, report_end_date)
                duration = 'Still Running' if not history_item['end_date'] else '%0.2f' % (
                    (parse(history_item['end_date']) - parse(history_item['start_date'])).total_seconds() / 3600.0)
                applicable_hours = 0 if not applicable_duration else '%0.2f' % (
                    (applicable_duration.total_seconds() * int(history_item['cpu'])) / 3600.0)
                writer.writerow({
                    'Username': user_name,
                    'Instance_ID': history_item['instance_id'],
                    'Instance_Status_History_ID': history_item['ih_id'],
                    'CPU': history_item['cpu'],
                    'Memory': history_item['mem'],
                    'Disk': history_item['disk'],
                    'Instance_Status_Start_Date': history_item['start_date'],
                    'Instance_Status_End_Date': history_item['end_date'],
                    'Report_Start_Date': report_start_date,
                    'Report_End_Date': report_end_date,
                    'Instance_Status': history_item['status'].title(),
                    'Duration (hours)': duration,
                    'Applicable_Duration (hours)': applicable_hours
                })


def calculate_applicable_duration(history_item, report_start_date, report_end_date):
    if not __validate_parameters(history_item, report_start_date, report_end_date):
        return 0

    if history_item['status'] != 'active':
        return 0

    start_date = parse(history_item['start_date'])
    if start_date > report_end_date:
        return 0
    if history_item['end_date']:
        end_date = parse(history_item['end_date'])
        if end_date < report_start_date:
            return 0
    else:
        end_date = None
    # Time delta calculations
    effective_start_date = max(start_date, report_start_date)
    effective_end_date = report_end_date if end_date is None else min(end_date, report_end_date)
    applicable_duration = effective_end_date - effective_start_date
    return applicable_duration


def __validate_parameters(history_item, report_start_date, report_end_date):
    if not history_item:
        logger.warning('History Item not present')
        return False

    if not report_start_date:
        logger.warning('report_start_date not present')
        return False

    if not report_end_date:
        logger.warning('report_end_date not present')
        return False

    if type(report_end_date) != datetime:
        logger.warning('type mismatch. Report End Date is not a datetime object')
        return False

    if type(report_start_date) != datetime:
        logger.warning('type mismatch. Report Start Date is not a datetime object')
        return False

    if report_start_date >= report_end_date:
        logger.warning('report_start_date more than report_end_date')
        return False

    if 'start_date' not in history_item:
        logger.warning('start date missing from history item for instance %s' % history_item['instance_id'])
        return False

    start_date_string = history_item['start_date']
    if not start_date_string:
        logger.warning('Start Date is not available for instance %s' % history_item['instance_id'])
        return False

    try:
        start_date = parse(start_date_string)
    except:
        logger.warning('Star Date is invalid')
        # Invalid start_date.
        # TODO: Log?
        return False

    if 'end_date' not in history_item:
        logger.warning('End Date is not available for instance %s' % history_item['instance_id'])
        return False
    else:
        end_date_string = history_item['end_date']
        if end_date_string:
            try:
                end_date = parse(end_date_string)
            except:
                logger.warning('End Date is invalid for instance %s' % history_item['instance_id'])
                # Invalid end date.
                # TODO: Log?
                return False
            if start_date > end_date:
                logger.warning('Start Date is more than end date')
                return False

    return True


def format_date(date):
    return date.strftime('%x').replace('/', '_')


if __name__ == '__main__':
    try:
        db_user = os.environ['ATMO_DBUSER']
        db_password = os.environ['ATMO_DBPASSWORD']
        db_host = os.environ['ATMO_DBHOST']
        db_port = os.environ['ATMO_DBPORT']
        db_name = os.environ['ATMO_DBNAME']
        report_start_string = sys.argv[1]
        report_end_string = sys.argv[2]
        try:
            username_to_filter = sys.argv[3]
        except:
            username_to_filter = None

        report_start_date = parse(report_start_string)
        report_end_date = parse(report_end_string)
    except:
        print
        print 'Usage:'
        print
        print 'export ATMO_DBUSER=dummy_user'
        print 'export ATMO_DBPASSWORD=\'somepassword\''
        print 'export ATMO_DBHOST=127.0.0.1'
        print 'export ATMO_DBPORT=5432'
        print 'export ATMO_DBNAME=dbname'
        print 'python allocation_status_script.py 2016-04-01T00:00:00.0-07 2016-05-01T00:00:00.0-07'
        print
        raise

    db_connection_string = 'postgres://%s:%s@%s:%s/%s' % (db_user, db_password, db_host, db_port, db_name)

    write_instance_history_file(db_connection_string, report_start_date, report_end_date, 'status_history.csv',
                                username_to_filter)
    with open('status_history.csv', 'r') as status_history:
        allocation_usage, user_instance_history_data, sizes = calculate_user_allocation_usage(status_history,
                                                                                              report_start_date,
                                                                                              report_end_date)

    write_sizes_file(sizes, 'instance_sizes.csv')
    # TODO: allocation -> instance_hours; cpu_hours -> allocation_usage
    user_cpu_hours = calculate_cpu_hours(allocation_usage, sizes)
    print 'Total users in report: %d' % len(user_cpu_hours)
    total_cpu_hours = sum(user_cpu_hours.values())
    print 'Total CPU Hours: %0.2f' % total_cpu_hours
    write_allocation_usage_file(allocation_usage, user_cpu_hours, 'allocation_usage.csv')
    detailed_report_filename = '%s_%s_report.csv' % (format_date(report_start_date), format_date(report_end_date))
    write_detailed_report_file(user_instance_history_data, report_start_date, report_end_date, detailed_report_filename)
