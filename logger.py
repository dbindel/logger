#!/Users/dbindel/anaconda/bin/python

"""
Usage:
  logger [options] add [TITLE]
  logger [options] note [TITLE]
  logger [options] done [TITLE]
  logger [options] list [TITLE]
  logger [options] ls [TITLE]

Arguments:
  TITLE    Task description with any tags

Options:
  -f FILE, --file=FILE    Input log file name
  -o FILE, --output=FILE  Output log file name
  -p TIME, --prev=TIME    Minutes elapsed since start
  -a DATE, --after=DATE   Start date of list range
  -b DATE, --before=DATE  End date of list range
  --dry                   Dry run (do not save back updates)
"""

from docopt import docopt
from datetime import datetime, timedelta
from os.path import expanduser
import re
import yaml
import sys

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

    def update(self, desc=None, date=None, tags=None, rec=None):
        if rec is None:
            rec = self.recs[-1]
        if desc is not None:
            rec['desc'] = desc
        if date is not None:
            rec['date'] = date
        if tags is not None:
            rec['tags'] = tags

    def start(self, now=None):
        if now is None:
            now = datetime.now()
        rec = self.recs[-1]
        rec['tstamp'] = now

    def finish(self, now=None):
        if now is None:
            now = datetime.now()
        rec = self.recs[-1]
        rec['tfinish'] = now

    def elapsed(self, elapsed):
        now = datetime.now()
        self.start(now-timedelta(minutes=elapsed))
        self.finish(now)

    def note(self, note=None):
        if note is not None:
            rec = self.recs[-1]
            rec['note'] = note

    def _tags_filter(self, tags=None):
        if tags is None:
            def filter(rec):
                return True
            return filter
        allow_tags = []
        block_tags = []
        for tag in tags:
            if tag[0] == '~':
                block_tags.append(tag[1:])
            else:
                allow_tags.append(tag)
        def filter(rec):
            if not 'tags' in rec:
                return False
            dtags = {tag: True for tag in rec['tags']}
            return (all([tag in dtags for tag in allow_tags]) and
                    all([not tag in dtags for tag in block_tags]))
        return filter

    def _date_filter(self, adate=None, bdate=None):
        if adate is None and bdate is None:
            def filter(rec):
                return True
            return filter
        def filter(rec):
            if 'date' in rec:
                date = rec['date']
                return ((not adate or date >= adate) and
                        (not bdate or date <= bdate))
            return False
        return filter

    def print_terse(self, rec):
        if 'tags' in rec:
            tags = " +" + (" +".join(rec['tags']))
        else:
            tags = ""
        print('{date} {desc}{0}'.format(tags, **rec))

    def print_verbose(self, rec):
        print('---')
        self.print_terse(rec)
        if 'tfinish' in rec and 'tstamp' in rec:
            tdiff = rec['tfinish']-rec['tstamp']
            print('  Time: {0} m'.format(tdiff.seconds // 60))
        if 'note' in rec:
            print(rec['note'])

    def list(self, desc=None, adate=None, bdate=None,
             tags=None, verbose=True):
        filter_tags = self._tags_filter(tags)
        filter_date = self._date_filter(adate, bdate)
        for rec in self.recs:
            if filter_tags(rec) and filter_date(rec):
                if verbose:
                    self.print_verbose(rec)
                else:
                    self.print_terse(rec)


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
        m = re.match('(\d\d\d\d-\d\d-\d\d)(\S*)', desc)
        if m:
            date = parse_date(desc[m.start(0):m.end(0)])
            desc = desc[m.end(1):]
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


def elapsed_opt(time):
    return time and int(time)


def main():
    with open(expanduser('~/.logger.yml'), 'rt') as f:
        default_options = yaml.load(f)
    options = docopt(__doc__)

    if options['--file'] is not None:
        fname = options['--file']
    elif 'file' in default_options:
        fname = default_options['file']
    else:
        fname = 'current.yml'
    logger = Logger(fname)

    desc, tags, date = split_desc(options['TITLE'])
    elapsed = elapsed_opt(options['--prev'])

    if options['add'] or options['note']:
        logger.add(desc, date or datetime.today(), tags)
        logger.start()
        if elapsed is not None:
            logger.elapsed(elapsed)
        if options['note']:
            logger.note(sys.stdin.read(1024))
    elif options['done']:
        logger.update(desc, date, tags)
        logger.finish()
    elif options['list'] or options['ls']:
        if date:
            after = date
            before = date
        else:
            after = options['--after'] and parse_date(options['--after'])
            before = options['--before'] and parse_date(options['--before'])
        logger.list(desc, after, before, tags, verbose=options['list'])
    else:
        print(__doc__)
        return

    if options['--dry']:
        print("--- SAVE ---")
        logger.save()
    else:
        ofname = options['--output']
        if ofname is None:
            ofname = fname
        logger.save(ofname)


if __name__=="__main__":
    main()
