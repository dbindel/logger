#!/Users/dbindel/anaconda/bin/python

"""
Usage:
  logger [options] log [TITLE]
  logger [options] note [TITLE]
  logger [options] done [TITLE]
  logger [options] list [TITLE]
  logger [options] ls [TITLE]
  logger [options] clock [TITLE]
  logger [options] view

Arguments:
  TITLE    Task description with any tags

Options:
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

"""
A log file consists of YML records with the fields:

  date: Date of the entry (required)
  desc: Description of the task (required)
  note: Any notes
  tags: List of text tags
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

    def render(self, rec, verbose=False):
        "Render record as a string."
        args = self.style.copy()
        args.update(rec)
        args['tags'] = self._tag_string(rec)
        recs = self.formats['entry'].format(**args)
        if verbose and 'tfinish' in rec and 'tstamp' in rec:
            tdiff = rec['tfinish']-rec['tstamp']
            args['clock'] = timedelta(seconds=tdiff.seconds)
            recs += self.formats['clock'].format(**args)
        if verbose and 'note' in rec:
            if 'note' in rec:
                for line in rec['note'].splitlines():
                    recs += "\n  {0}".format(line)
        return recs

    def print(self, rec, verbose=False):
        "Print rendered record."
        print(self.render(rec, verbose=verbose))


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
    return 'tfinish' in rec and 'tstamp' in rec


def has_open_clock(rec):
    "Return true if record has a time stamp only."
    return not 'tfinish' in rec and 'tstamp' in rec


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

    def __init__(self, ifname, printer=None):
        "Load a log file with the given name."
        self.printer = printer or RecPrinter()
        with open(ifname, 'rt') as f:
            self.recs = yaml.load(f) or []

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
        for rec in self.filtered_recs(filters):
            self.printer.print(rec, verbose=verbose)

    def clock(self, filters=[]):
        "Compute time spent on a filtered list of records."
        result = timedelta(seconds=0)
        for rec in filter(has_clock, self.filtered_recs(filters)):
            tdiff = rec['tfinish']-rec['tstamp']
            result += tdiff
        return result

    def view(self):
        "View the last few records."
        print("\nRecent log items")
        print("----------------")
        recs = self.recs if len(self.recs) <= 5 else self.recs[-5:]
        for rec in recs:
            self.printer.print(rec, verbose=False)
        if self.recs and has_open_clock(self.recs[-1]):
            tdiff = datetime.now() - rec['tstamp']
            tdiff = timedelta(seconds=int(tdiff.total_seconds()))
            print("\nLast task open for: {0}".format(tdiff))


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
        'formats': {
            'entry': '{cyan}{date}{plain} {desc}{tags}',
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

    # Figure out filename and open logger file
    fname = options['--file'] or config_opt['log']
    printer = RecPrinter(config_opt['formats'], config_opt['style'])
    logger = Logger(fname, printer)

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

    # Dispatch command options
    if options['log'] or options['note']:
        logger.add(desc, date or today, tags)
        logger.start()
        elapsed = options['--prev']
        if elapsed is not None:
            logger.elapsed(int(elapsed))
        if options['note']:
            logger.note(sys.stdin.read(1024))
    elif options['done']:
        logger.update(desc, date, tags)
        logger.finish()
    elif options['list'] or options['ls']:
        logger.list(filters=filters, verbose=options['list'])
    elif options['clock']:
        logger.list(filters=filters, verbose=False)
        t = logger.clock(filters=filters)
        t = timedelta(seconds=int(t.total_seconds()))
        print("Total elapsed time: {0}".format(t))
    elif options['view']:
        logger.view()
    else:
        print(__doc__)
        return

    # Write back log
    logger.save(fname)


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
