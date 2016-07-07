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
  -f FILE, --file=FILE    Log file name
  -p TIME, --prev=TIME    Minutes elapsed since start
  -a DATE, --after=DATE   Start date of list range
  -b DATE, --before=DATE  End date of list range
  -t, --today             Add today's date stamp to title
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

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.style = ansi_codes.copy()
        self.fmt = "{cyan}{date}{plain} {desc}{tags}"
        self.tag_fmt = "{yellow}+{0}{plain}"
        if verbose:
            self.clock_fmt = " {brown}[{clock}]{plain}"
        else:
            self.clock_fmt = ""

    def _tag_string(self, rec):
        "Render record tags as a string."
        if not 'tags' in rec:
            return ""
        tags = [self.tag_fmt.format(tag, **self.style) for tag in rec['tags']]
        return " " + " ".join(tags)

    def render(self, rec):
        "Render record as a string."
        args = self.style.copy()
        args.update(rec)
        args['tags'] = self._tag_string(rec)
        recs = self.fmt.format(**args)
        if 'tfinish' in rec and 'tstamp' in rec:
            tdiff = rec['tfinish']-rec['tstamp']
            args['clock'] = timedelta(seconds=tdiff.seconds)
            recs += self.clock_fmt.format(**args)
        if self.verbose and 'note' in rec:
            for line in rec['note'].splitlines():
                recs += "\n  {0}".format(line)
        return recs

    def print(self, rec):
        "Print rendered record."
        print(self.render(rec))


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

    def __init__(self, ifname):
        with open(ifname, 'rt') as f:
            self.recs = yaml.load(f)
        if self.recs is None:
            self.recs = []

    def save(self, ofname=None):
        if ofname is None:
            print(yaml.dump(self.recs, default_flow_style=False))
        else:
            with open(ofname, 'wt') as f:
                yaml.dump(self.recs, f, default_flow_style=False)

    def add(self, desc=None, date=None, tags=None):
        rec = {}
        self.recs.append(rec)
        self.update(desc, date, tags)
        return rec

    def update(self, desc=None, date=None, tags=None):
        rec = self.recs[-1]
        if desc is not None:
            rec['desc'] = desc
        if date is not None:
            rec['date'] = date
        if tags is not None:
            rec['tags'] = tags

    def start(self, now=None):
        self.recs[-1]['tstamp'] = now or datetime.now()

    def finish(self, now=None):
        self.recs[-1]['tfinish'] = now or datetime.now()

    def elapsed(self, elapsed):
        now = datetime.now()
        self.start(now-timedelta(minutes=elapsed))
        self.finish(now)

    def note(self, note=None):
        if note is not None:
            self.recs[-1]['note'] = note

    def filtered_recs(self, filters):
        recs = self.recs
        for f in filters:
            recs = filter(f, recs)
        return recs

    def list(self, filters=[], verbose=True):
        printer = RecPrinter(verbose=verbose)
        for rec in self.filtered_recs(filters):
            printer.print(rec)

    def clock(self, filters=[]):
        result = timedelta(seconds=0)
        for rec in filter(has_clock, self.filtered_recs(filters)):
            tdiff = rec['tfinish']-rec['tstamp']
            result += tdiff
        return result

    def view(self):
        print("\nRecent log items")
        print("----------------")
        printer = RecPrinter(verbose=False)
        recs = self.recs if len(self.recs) <= 5 else self.recs[-5:]
        for rec in recs:
            printer.print(rec)
        if self.recs and has_open_clock(self.recs[-1]):
            tdiff = datetime.now() - rec['tstamp']
            tdiff = timedelta(seconds=tdiff.seconds)
            print("\nLast task open for: {0}".format(tdiff))


# ==================================================================
# Parsing and main routine


def parse_date(s):
    dtime = datetime.strptime(s, "%Y-%m-%d")
    return dtime.date()


def split_desc(desc=None):
    if desc is None:
        date = None
        desc = None
        tags = None
    else:

        # Split date from front
        m = re.match('(\d\d\d\d-\d\d-\d\d)(\s*)', desc)
        if m:
            date = parse_date(desc[m.start(1):m.end(1)])
            desc = desc[m.end(2):]
        else:
            date = None

        # Split tags from end
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


def main():

    # Read configuration file
    with open(expanduser('~/.logger.yml'), 'rt') as f:
        default_options = yaml.load(f)

    # Parse options
    options = docopt(__doc__)

    # Figure out filename and open logger file
    if options['--file'] is not None:
        fname = options['--file']
    elif 'file' in default_options:
        fname = default_options['file']
    else:
        fname = 'current.yml'
    logger = Logger(fname)

    # Split description
    today = datetime.today().date()
    desc, tags, date = split_desc(options['TITLE'])
    if date is None and options['--today']:
        date = today

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
        t = timedelta(seconds=t.seconds)
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
