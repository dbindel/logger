#!/Users/dbindel/anaconda/bin/python
"""
Usage:
  logger [options] add [TITLE]
  logger [options] note [TITLE]
  logger [options] done [TITLE]
  logger [options] list [TITLE]
  logger [options] ls [TITLE]

Arguments:
  TITLE    Task description

Options:
  -f FILE, --file=FILE    Input log file name
  -o FILE, --output=FILE  Output log file name
  -d DATE, --date=DATE    Override date
  -t TAGS, --tags=TAGS    Add tags
  -p TIME, --prev=TIME    Minutes elapsed since start
  -a DATE, --after=DATE   Start date of list range
  -b DATE, --before=DATE  End date of list range
"""

from docopt import docopt
from datetime import datetime, timedelta
from os.path import expanduser
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
            yaml.dump(self.recs, f, default_flow_style=False)
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
            rec['date'] = date.strftime('%Y-%m-%d')
        if tags is not None:
            rec['tags'] = tags

    def start(self, now=None):
        if now is None:
            now = datetime.now()
        rec = self.recs[-1]
        rec['tstamp'] = now.isoformat(' ')

    def finish(self, now=None):
        if now is None:
            now = datetime.now()
        rec = self.recs[-1]
        rec['tfinish'] = now.isoformat(' ')

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
        adates = '0000-00-00' if adate is None else adate
        bdates = '9999-99-99' if bdate is None else bdate
        def filter(rec):
            if 'date' in rec:
                dates = rec['date'].strftime('%Y-%m-%d')
                return dates >= adates and dates <= bdates
            return False
        return filter

    def list(self, desc=None, adate=None, bdate=None,
             tags=None, fmt=None, verbose=True):
        filter_tags = self._tags_filter(tags)
        filter_date = self._date_filter(adate, bdate)
        for rec in self.recs:
            if filter_tags(rec) and filter_date(rec):
                if verbose:
                    print('---')
                print('{date}: {desc}'.format(**rec))
                if verbose and 'tags' in rec:
                    print('  Tags: {0}'.format(rec['tags']))
                if verbose and 'tfinish' in rec and 'tstamp' in rec:
                    dfmt = '%Y-%m-%d %H:%M:%S.%f'
                    tfinish = datetime.strptime(rec['tfinish'], dfmt)
                    tstart  = datetime.strptime(rec['tstamp'], dfmt)
                    tdiff = tfinish-tstart
                    print('  Time: {0} m'.format(tdiff.seconds // 60))
                if verbose and 'note' in rec:
                    print(rec['note'])


def date_opt(dtime):
    if dtime is None:
        dtime = datetime.today()
    else:
        try:
            dtime = datetime.strptime(dtime, '%Y-%m-%d %H:%M')
        except:
            dtime = datetime.strptime(dtime, '%Y-%m-%d')
    return dtime


def file_opt(fname):
    if fname is None:
        fname = 'current.yml'
    return fname


def tags_opt(tags):
    if tags is None:
        return None
    return tags.split()


def elapsed_opt(time):
    if time is None:
        return None
    return int(time)


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

    desc = options['TITLE']
    dtime = date_opt(options['--date'])
    tags = tags_opt(options['--tags'])
    elapsed = elapsed_opt(options['--prev'])

    if options['add'] or options['note']:
        logger.add(desc, dtime, tags)
        logger.start()
        if elapsed is not None:
            logger.elapsed(elapsed)
        if options['note']:
            logger.note(sys.stdin.read(1024))
    elif options['done']:
        ldate = None if options['--date'] is None else dtime
        logger.update(desc, ldate, tags)
        logger.finish()
    elif options['list'] or options['ls']:
        if options['--date'] is not None:
            after = dtime
            before = dtime
        else:
            after = options['--after']
            before = options['--before']
        logger.list(desc, after, before, tags, verbose=options['list'])
    else:
        print(__doc__)
        return

    ofname = options['--output']
    if ofname is None:
        ofname = fname
    logger.save(ofname)


if __name__=="__main__":
    main()
