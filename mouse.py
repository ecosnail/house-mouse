#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# core library modules
import sys, argparse, sqlite3, time

# 3rd party modules
from tabulate import tabulate

class Action(object):
    List = 'list'
    Add = 'add'
    Input = 'input'

def prompt_yes_or_no(
        prompt=u'Подтвердите',
        confirmed=u'Подтверждено',
        declined=u'Отменено'):
    yes_or_no = ''
    while yes_or_no not in ['y', 'n']:
        sys.stdout.write(prompt + u' (y/n): ')
        yes_or_no = raw_input()

    if yes_or_no == 'y':
        print confirmed
        return True
    else:
        print declined
        return False

def query_cursor(db, query_string, query_args=None):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(query_string, query_args)
    return cursor

def query_all(db, query_string, query_args=None):
    return query_cursor(db, query_string, query_args).fetchall()

def query_one(db, query_string, query_args=None):
    return query_cursor(db, query_string, query_args).fetchone()

def timestamp_str(timestamp):
    TIME_FORMAT = '%d.%m.%Y %H:%M:%S'
    return time.strftime(TIME_FORMAT, time.localtime(timestamp))

def action_list_counters(args):
    rows = query_all(args.db, r'''
        select CounterLabel, CounterName
        from Counter
        order by CounterLabel;
    ''')
    print
    print tabulate(rows, headers=['ID', u'Счётчик'])

def action_list_inputs(args):
    cursor = query_cursor(args.db, r'''
        select
            InputId,
            InputTime,
            ToolName || ' (' || ToolLabel || ')'
        from Input
        join InputTool using (ToolId)
    ''')

    for src_row in cursor:
        rows.append([src_row[0], timestamp_str(src_row[1]), src_row[2]])

    print
    print tabulate(rows, headers=[u'ID ввода', u'Время ввода (местное)', u'Инструмент ввода'])


def action_input(args):
    conn = sqlite3.connect(args.db)
    c = conn.cursor()

    values = {}
    for counter_id, label, name in c.execute(
            r'select CounterId, CounterLabel, CounterName from Counter order by CounterLabel;'):
        sys.stdout.write(u'  {0:21} | {1:13}: '.format(name, label))
        values[counter_id] = raw_input()

    # Confirm data input
    yes_or_no = ''
    while yes_or_no not in ['y', 'n']:
        sys.stdout.write(u'Подтвердите ввод (y/n): ')
        yes_or_no = raw_input()
    if yes_or_no != 'y':
        return
    print u'Ввод подтверждён'

    # Get ID for the CLI client
    c.execute(r'''
        select ToolId from InputTool where ToolLabel = 'cli'
    ''')
    tool_id = c.fetchone()[0]

    # Use UNIX timestamp (seconds since the epoch in UTC)
    timestamp = int(time.time())

    c.execute(r'''
        insert into Input (ToolId, InputTime)
        values (?, ?);
    ''', (tool_id, timestamp))

    c.execute('select last_insert_rowid();')
    input_id = c.fetchone()[0]

    # Insert actual measurement values. Order is undefined, and is not
    # important.
    for counter_id, value in values.iteritems():
        c.execute(r'''
            insert into Measure (CounterId, MeasureTime, InputId, Value)
            values (?, ?, ?, ?);
        ''', (counter_id, timestamp, input_id, value))

    conn.commit()

def action_remove_input(args):
    input_id, input_time, tool_name, tool_label = query_one(args.db, r'''
        select
            InputId, InputTime, ToolName, ToolLabel
        from Input
        join InputTool using (ToolId)
        where InputId = ?;
    ''', (args.input_id,))

    measures = query_all(args.db, r'''
        select
            MeasureId, MeasureTime, MeasureValue, CounterName, CounterLabel
        from Measure
        join Counter using (CounterId)
        where InputId = ?;
    ''', (args.input_id,))

    table = []
    for measure_id, measure_time, measure_value, counter_name, counter_label in measures:
        table.append([
            measure_id,
            timestamp_str(measure_time),
            measure_value,
            counter_name + ' (' + counter_label + ')'
        ])

    print u'Будут удалены данные ввода ({})'.format(input_id)
    print u'  Произведённого:        {}'.format(timestamp_str(input_time))
    print u'  С помощью инструмента: {} ({})'.format(tool_name, tool_label)
    print
    print u'А именно, следующие измерения:'
    print
    print tabulate(table, headers=[
        u'ID измерения',
        u'Время измерения',
        u'Значение измерения',
        u'Счётчик'])
    print

    if not prompt_yes_or_no(
            u'Подтвердите удаление данных',
            u'Удаление данных подтверждено',
            u'Удаление данных отменено'):
        return

    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    cursor.execute(r'''
        delete from Measure
        where InputId = ?;
    ''', (input_id,))
    cursor.execute(r'''
        delete from Input
        where InputId = ?;
    ''', (input_id,))

    conn.commit()

    print u'Данные удалены'


def action_help(args):
    if args.command == 'list':
        parser_list.print_help()
    else:
        parser.print_help()


if __name__ == '__main__':
    try:
        # mouse ...
        parser = argparse.ArgumentParser(description=u'''Господский тул для
            управления HouseMouse из консоли. Для получения справки по команде
            COMMAND, наберите 'mouse help COMMAND' или 'mouse COMMAND -h'.''')
        parser.add_argument('--db', metavar='DATABASE', dest='db',
            default='house.db', help=u'Файл базы данных')
        parser_sub = parser.add_subparsers(metavar='ACTION',
            help=u'Действие')

        # mouse help
        parser_help = parser_sub.add_parser('help',
            help=u'Справка по команде')
        parser_help.add_argument('command', nargs='?',
            help=u'Команда, для которой нужно вывести справку')
        parser_help.set_defaults(func=action_help)
        
        # mouse list ...
        parser_list = parser_sub.add_parser('list',
            help=u'Вывести какие-либо данные')
        parser_list_sub = parser_list.add_subparsers(metavar='ITEM',
            help=u'Какого рода данные нужно вывести?')

        # mouse list counters
        parser_list_counters = parser_list_sub.add_parser('counters',
            help=u'Вывести информацию о счётчиках')
        parser_list_counters.set_defaults(func=action_list_counters)

        # mouse list inputs
        parser_list_inputs = parser_list_sub.add_parser('inputs',
            help=u'Информация о вводе данных')
        parser_list_inputs.set_defaults(func=action_list_inputs)

        # mouse input
        parser_input = parser_sub.add_parser('input',
            help='Interactively input measurements to DB')
        parser_input.set_defaults(func=action_input)

        # mouse remove ...
        parser_remove = parser_sub.add_parser('remove',
            help=u'Безвозвратно удалить какие-либо данные из базы')
        parser_remove_sub = parser_remove.add_subparsers(metavar='OBJECT',
            help=u'Удалить что?')

        # mouse remove input
        parser_remove_input = parser_remove_sub.add_parser('input',
            help=u'Удалить результаты ввода данных. Позволяет откатить неудачную операцию input.')
        parser_remove_input.add_argument('input_id', type=int,
            metavar=u'ID_ВВОДА',
            help=u'Идентификатор ввода, результаты которого потребно удалить')
        parser_remove_input.set_defaults(func=action_remove_input)

        args = parser.parse_args()
        args.func(args)

    except RuntimeError as e:
        sys.stderr.write(str(e))
