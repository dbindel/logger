#!/Users/dbindel/anaconda/bin/python

"""
Usage:
  logger [options]
  logger [options] view
  logger [options] list [TITLE]
  logger [options] ls [TITLE]
  logger [options] cal [TITLE]
  logger [options] clock [TITLE]
  logger [options] add [TITLE]
  logger [options] del [ID]
  logger [options] do [ID]
  logger [options] log [TITLE]
  logger [options] done [TITLE]
  logger [options] catch [TITLE]
  logger [options] notes [TITLE]

Arguments:
  TITLE    Task description with any tags
  ID       Task identifier from to-do list

Options:
  -n, --note                 Add note field
  -c MINS, --clock=MINS      Minutes clocked
  -f FILE, --file=FILE       Log file name
  -p TIME, --prev=TIME       Minutes elapsed since start
  -a DATE, --after=DATE      Start date of list range
  -b DATE, --before=DATE     End date of list range
  -y DAYS, --yesterday=DAYS  Use date stamp from DAYS ago
  -t, --today                Add today's date stamp to title
"""

from docopt import docopt
from datetime import datetime, timedelta
from os.path import expanduser
import re
import yaml
import sys
import copy

"""
A log file consists of YML records with the fields:

  date: Date of the entry (required)
  desc: Description of the task (required)
  note: Any notes
  tags: List of text tags
  tclock: Minutes clocked (overrides tstamp/tfinish)
  tstamp: Time stamp when log entry was added
  tfinish: Time stamp when log entry was marked done

Additional fields may be added as appropriate.  On input and output,
log entries have a compact form inspired by todo.txt

  2016-07-04 This is the description +tag1 +tag2
"""


# ==================================================================
# Formatting functions


# ANSI code info stolen from
#  https://github.com/bram85/topydo/blob/master/topydo/lib/Color.py
#  http://bluesock.org/~willg/dev/ansi.html
#
ansi_codes = {
    'plain'        : '\033[0m',
    'black'        : '\033[0;30m',
    'blue'         : '\033[0;34m',
    'green'        : '\033[0;32m',
    'cyan'         : '\033[0;36m',
    'red'          : '\033[0;31m',
    'purple'       : '\033[0;35m',
    'brown'        : '\033[0;33m',
    'gray'         : '\033[0;37m',
    'dark-gray'    : '\033[1;30m',
    'light-blue'   : '\033[1;34m',
    'light-green'  : '\033[1;32m',
    'light-cyan'   : '\033[1;36m',
    'light-red'    : '\033[1;31m',
    'light-purple' : '\033[1;35m',
    'yellow'       : '\033[1;33m',
    'white'        : '\033[1;37m'
}


class RecPrinter(object):
    """Format log records for printing.

    Attributes:
      style:     Dictionary of elements for format strings
      fmt:       Basic record format strings
      tag_fmt:   Format for one tag
      clock_fmt: Format for elapsed time clock
    """

    def __init__(self, formats={}, style={}):
        self.style = ansi_codes.copy()
        self.formats = {
            'entry': '{cyan}{date}{plain} {desc}{tags}',
            'cal':   '  {desc}{tags}',
            'tag':   '{yellow}+{0}{plain}',
            'clock': ' {brown}[{clock}]{plain}'
        }
        self.style.update(style)
        self.formats.update(formats)

    def _tag_string(self, rec):
        "Render record tags as a string."
        if not 'tags' in rec:
            return ""
        tags = [self.formats['tag'].format(tag, **self.style)
                for tag in rec['tags']]
        return " " + " ".join(tags)

    def render(self, rec, verbose=False, fmt='entry'):
        "Render record as a string."
        args = self.style.copy()
        args.update(rec)
        args['tags'] = self._tag_string(rec)
        recs = self.formats[fmt].format(**args)
        if verbose and 'tclock' in rec:
            args['clock'] = timedelta(seconds=60*rec['tclock'])
            recs += self.formats['clock'].format(**args)
        elif verbose and has_clock(rec):
            args['clock'] = timedelta(seconds=rec_clock(rec).seconds)
            recs += self.formats['clock'].format(**args)
        if verbose and 'note' in rec:
            if 'note' in rec:
                for line in rec['note'].splitlines():
                    recs += "\n  {0}".format(line)
        return recs

    def print(self, rec, verbose=False, fmt='entry'):
        "Print rendered record."
        print(self.render(rec, verbose=verbose, fmt=fmt))


# ==================================================================
# Clock functions


def rec_clock(rec):
    if 'tclock' in rec:
        return timedelta(seconds=60*rec['tclock'])
    elif 'tfinish' in rec and 'tstamp' in rec:
        return rec['tfinish']-rec['tstamp']


def parse_clock(c):
    cs = c.split(':')
    if len(cs) == 1:
        return int(cs[0])
    elif len(cs) == 2:
        return 60*int(cs[1])+int(cs[0])
    else:
        raise ValueError('Wrong clock argument')


# ==================================================================
# Filtering functions


def date_filter(adate=None, bdate=None):
    "Return filter to check if record dates are in [adate, bdate]."
    if adate is None and bdate is None:
        return None
    def f(rec):
        return ((adate is None or rec['date'] >= adate) and
                (bdate is None or rec['date'] <= bdate))
    return f


def tags_filter(tags=None):
    "Return filter to check if records match tags spec."
    if tags is None:
        return None
    def f(rec):
        if not 'tags' in rec:
            return False
        dtags = {tag: True for tag in rec['tags']}
        return not any(((tag[0] == "~" and tag[1:] in dtags) or
                        (tag[0] != "~" and not tag in dtags)
                        for tag in tags))
    return f


def has_clock(rec):
    "Return true if record has a closed clock."
    return 'tclock' in rec or ('tfinish' in rec and 'tstamp' in rec)


def has_open_clock(rec):
    "Return true if record has a time stamp only."
    return not 'tfinish' in rec and not 'tclock' in rec and 'tstamp' in rec


# ==================================================================
# Log manager


class Logger(object):
    """Manage a log file.

    Provides some basic functionality to load/save a log file,
    add records, and report on log contents.

    Attributes:
      printer: RecPrinter object used for output
      recs: Record list
    """

    def __init__(self, ifname=None, recs=None, printer=None):
        "Load log data from a file or an existing data structure."
        self.printer = printer or RecPrinter()
        if recs:
            self.recs = self.recs
        else:
            try:
                with open(ifname, 'rt') as f:
                    self.recs = yaml.load(f) or []
            except FileNotFoundError:
                self.recs = []

    def save(self, ofname=None):
        "Write back a log file."
        with open(ofname, 'wt') as f:
            yaml.dump(self.recs, f, default_flow_style=False)

    @property
    def last(self):
        "Get the last log entry."
        return self.recs[-1]

    def add(self, desc=None, date=None, tags=None):
        "Add a new record and set the basic fields."
        self.recs.append({})
        self.update(desc, date, tags)
        return self.last

    def update(self, desc=None, date=None, tags=None):
        "Update record."
        rec = self.last
        if desc is not None:
            rec['desc'] = desc
        if date is not None:
            rec['date'] = date
        if tags is not None:
            rec['tags'] = tags

    def start(self, now=None):
        "Add time stamp to last; if none explicitly given, use current time."
        self.last['tstamp'] = now or datetime.now()

    def finish(self, now=None):
        "Add finish time to last; if none explicitly given, use current time."
        self.last['tfinish'] = now or datetime.now()

    def elapsed(self, elapsed):
        "Mark last record as starting elapsed minutes ago (finishing now)."
        now = datetime.now()
        self.start(now-timedelta(minutes=elapsed))
        self.finish(now)

    def note(self, note=None):
        "Add note to last record."
        if note is not None:
            self.last['note'] = note

    def filtered_recs(self, filters=[]):
        "Return a filtered list of records."
        recs = self.recs
        for f in filters:
            recs = filter(f, recs)
        return recs

    def list(self, filters=[], verbose=True):
        "Print a filtered list of records."
        count = 0
        for rec in self.filtered_recs(filters):
            r = rec.copy()
            r['count'] = count
            count += 1
            self.printer.print(r, verbose=verbose)

    def calendar(self, filters=[], verbose=True):
        "Print a filtered list of records in calendar form."
        count = 0
        pdate = None
        for rec in self.filtered_recs(filters):
            r = rec.copy()
            r['count'] = count
            count += 1
            if not pdate or pdate != rec['date']:
                print(" ")
                print(rec['date'].strftime('%Y-%m-%d %a'))
                print("--------------")
            self.printer.print(r, verbose=verbose, fmt='cal')
            pdate = rec['date']
        print(" ")

    def clock(self, filters=[]):
        "Compute time spent on a filtered list of records."
        result = timedelta(seconds=0)
        for rec in filter(has_clock, self.filtered_recs(filters)):
            result += rec_clock(rec)
        return result

    def view(self):
        "View the last few records."
        recs = self.recs if len(self.recs) <= 5 else self.recs[-5:]
        for rec in recs:
            self.printer.print(rec, verbose=False)
        if self.recs and has_open_clock(self.last):
            tdiff = datetime.now() - rec['tstamp']
            tdiff = timedelta(seconds=int(tdiff.total_seconds()))
            print("\nLast task open for: {0}".format(tdiff))


# ==================================================================
# To-do file manager

class TodoLogger(Logger):
    """Manage a todo file.

    Attributes:
      printer: RecPrinter object used for output
      recs: Todo record list
    """

    def __init__(self, ifname, printer=None):
        self.printer = printer or RecPrinter()
        with open(ifname, 'rt') as f:
            self.__data = yaml.load(f) or {}
        self.recs = self.__data.get('todo', [])
        self.rules = self.__data.get('scheduled', [])
        self.run_rules()

    def run_rules(self):
        "Run rule"
        for rule in self.rules:
            if rule.get('active', True):
                self.run_rule(rule)
        self.rules = [rule for rule in self.rules if rule.get('active', True)]

    def run_rule(self, rule):
        "Run scheduler rule"
        today = datetime.today().date()
        if 'date' in rule and today >= rule['date']:
            rec = copy.deepcopy(rule)
            if 'repeat' in rule:
                del rec['repeat']
                rule['date'] += timedelta(days=rule['repeat'])
            else:
                rule['active'] = False
            self.recs.append(rec)

    def save(self, ofname=None):
        "Write back a todo file."
        self.__data['todo'] = self.recs
        self.__data['scheduled'] = self.rules
        with open(ofname, 'wt') as f:
            yaml.dump(self.__data, f, default_flow_style=False)

    def add(self, desc=None, date=None, tags=None):
        "Add a new record and set the basic fields."
        self.recs.append({})
        self.update(desc, date, tags)
        rec = self.last
        if date > datetime.today().date():
            self.rules.append(rec)
            del self.recs[-1]


# ==================================================================
# Parsing date strings and title strings


def parse_date(s):
    "Convert a text date string into a datetime.date"
    dtime = datetime.strptime(s, "%Y-%m-%d")
    return dtime.date()


def split_desc(desc=None):
    "Split a title string into date, description, and tags."
    if desc is None:
        return (None, None, None)
    m = re.match('(\d\d\d\d-\d\d-\d\d)(\s*)', desc)
    if m:
        date = parse_date(desc[m.start(1):m.end(1)])
        desc = desc[m.end(2):]
    else:
        date = None
    l = desc.split(" +")
    if len(l[0]) == 0:
        desc = None
        tags = None
    elif l[0][0] == "+":
        l[0] = l[0][1:]
        desc = None
        tags = l
    elif len(l) == 1:
        desc = l[0]
        tags = None
    else:
        desc = l[0]
        tags = l[1:]
    return (desc, tags, date)


# ==================================================================
# Main routine

def get_config(fname):
    "Read configuration information on top of defaults."
    opt = {
        'log': 'log.yml',
        'todo': 'todo.yml',
        'formats': {
            'entry': '{cyan}{date}{plain} {desc}{tags}',
            'cal':   '  {desc}{tags}',
            'tag':   '{yellow}+{0}{plain}',
            'clock': ' {brown}[{clock}]{plain}'
        },
        'style': {}
    }
    with open(expanduser(fname), 'rt') as f:
        opt.update(yaml.load(f))
    return opt


def main():

    # Parse options
    config_opt = get_config('~/.logger.yml')
    options = docopt(__doc__)

    # Figure out filename and open logger and catch file
    fname = options['--file'] or config_opt['log']
    cname = config_opt['catch']
    style = config_opt['style']
    lformats = config_opt['formats']
    printer = RecPrinter(lformats, style)
    logger = Logger(fname, printer=printer)
    catch = Logger(cname, printer=printer)

    # Open todo file
    tformats = lformats.copy()
    tformats['entry'] = '{count}. {desc}{tags}'
    todo = TodoLogger(config_opt['todo'], printer=RecPrinter(tformats, style))

    # Split description
    today = datetime.today().date()
    desc, tags, date = split_desc(options['TITLE'])

    # Set date based on flags
    if date is None and options['--today']:
        date = today
    if date is None and options['--yesterday']:
        date = today-timedelta(days=int(options['--yesterday']))

    # Set up any filters
    after  = options['--after']
    before = options['--before']
    after  = after and parse_date(after)
    before = before and parse_date(before)
    filters = [tags_filter(tags),
               date_filter(date, date),
               date_filter(after, before)]

    # Set clock / tfinish from command line
    def set_clock(done=False):
        if options['--prev']:
            logger.elapsed(parse_clock(options['--prev']))
        elif options['--clock']:
            logger.last['tclock'] = parse_clock(options['--clock'])
        elif done:
            logger.finish()

    # Dispatch command options
    if options['add']:
        todo.add(desc, date or today, tags)
    elif options['del']:
        del todo.recs[int(options['ID'])]
    elif options['do']:
        id = int(options['ID'])
        rec = todo.recs[id].copy()
        del todo.recs[id]
        rec['date'] = today
        logger.recs.append(rec)
        logger.start()
        set_clock()
    elif options['log']:
        logger.add(desc, date or today, tags)
        logger.start()
        set_clock()
    elif options['done']:
        logger.update(desc, date, tags)
        set_clock(True)
    elif options['catch']:
        catch.add(desc, date or today, tags)
        catch.start()
    elif options['list'] or options['ls']:
        logger.list(filters=filters, verbose=options['list'])
    elif options['notes']:
        catch.list(filters=filters, verbose=True)
    elif options['cal']:
        logger.calendar(filters=filters, verbose=False)
    elif options['clock']:
        logger.list(filters=filters, verbose=False)
        t = logger.clock(filters=filters)
        t = timedelta(seconds=int(t.total_seconds()))
        print("Total elapsed time: {0}".format(t))
    else:
        print("\nTo-do items")
        print("-------------")
        todo.list(verbose=False)
        print("\nRecent log items")
        print("----------------")
        logger.view()
        print(" ")

    # Add note if requested
    def get_note():
        print("Enter note text (end with Ctrl-D):")
        return sys.stdin.read(1024)

    if options['--note']:
        if options['add']:
            todo.note(get_note())
        elif options['do'] or options['log'] or options['done']:
            logger.note(get_note())
        elif options['catch']:
            catch.note(get_note())
        else:
            print("Cannot add note for this command")

    # Write back files
    logger.save(fname)
    catch.save(cname)
    todo.save(config_opt['todo'])


# ==================================================================
# Boilerplate and YAML rejiggering


# See http://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)


if __name__=="__main__":
    main()
