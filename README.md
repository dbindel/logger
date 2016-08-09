# Logging

> The days are long, but the years are short.

I know that I forget things.  So I keep records, though my records have
changed form over time.  Sometimes, I have used pen and paper; I love
pens and paper, and find ideas like [bullet journals] appealing.  But I
also like digit searching and slicing tools, and I'm a fast typist. I am
a fan of plain text over tools like Evernote or Google Keep, and have
tried [org mode] and [todo.txt] files for long periods. But though I
love Emacs, I do not love Org mode.  And though I think [todo.txt] is
awesome, I want to track my days as well as upcoming tasks.

This framework is my current attempt at keeping track.  It is not
perfect, but it is extensible.  The basic entities are tasks, log
entries, and notes.  All have a date, a description, organizing tags,
and an optional note.  Log entries also have a time stamp, and optional
end time or clock fields to track the time spent.  All entries are
stored in YAML files.  These can be edited as text, and I keep them
under version control.  There is also a command line utility to manage
the files.

Organization is a personal thing, and this is a personal tool.
Nonetheless, I am putting it in a public repository in case it does
anyone else any good.

[bullet journals]: http://bulletjournal.com/
[todo.txt]: http://todotxt.com/
[org mode]: http://orgmode.org/

# The command line interface

The command line interface is implemented in `logger.py`.  I alias this
to a single character (`t`).  Many commands take a description string,
consisting of an (optional) date, a plain text description, optional
field definitions (`foo:bar`) and a set of context tags with the form
`+tagname`.  A tag name of the form `+~tagname` is used in queries to
find all log entries that do not match a given tag. Otherwise, the
common options are:

 - `-c MINS`: Minutes spent on a log entry
 - `-f FILE`: Alternate log file (mostly for debugging)
 - `-x FILE`: Alternate collection
 - `-p MINS`: Minutes before the present that a log entry started
 - `-a DATE`: Start date for a query range
 - `-b DATE`: End date for a query range
 - `-y DAYS`: Days before today (date specification)
 - `-t`:      Today (date specification)
 - `-n`:      Add note to an entry
 - `-l FILE`: Add a long note to an entry (points to a new file)

The basic commands for the logger CLI are:

## Task management

 - `t add [DESC]`: Add a task to the task list
 - `t del [ID]`:   Remove a task from the task list
 - `t do [ID]`:    Move a task from the task list to the log

## Log management

 - `t log [DESC]`:  Add a log entry
 - `t done [DESC]`: Update last log entry data and closing time stamp

## Log inquiries

With no arguments, `t` is equivalent to `t view`.

 - `t view [DESC]`:  View the current task list and last five log entries
 - `t ls [DESC]`:    List all log entries matching the date/tag filters
 - `t list [DESC]`:  Like `ls`, but also show clock information and notes
 - `t cal [DESC]`:   Show log entries under date/weekday subheadings
 - `t clock [DESC]`: Total times for all matching log entries

# File formats

There are four main files, all of which use YAML formatting conventions.

## Configuration

The configuration file is at `~/.logger.yml`.  It specifies paths to
a log file and a todo file, e.g.

    log:   /my/log.yml
    todo:  /my/todo.yml

In addition, the configuration file may specify collections
(specialized log files).  Collections have a description,
a file name, and an optional sort key.

    collections:
      books:
        desc: Books I have read
        file: /my/books.yml
      catch:
        desc: Caught notes
        file: /my/catch.yml
      dates:
        desc: Significant upcoming dates
        file: /my/dates.yml
        sort: date
      miles:
        desc: Personal milestones
        file: /my/milestones.yml
        sort: date

## Log file

The log file consists of a list of records with the following fields:

 - date: Day of the logged item
 - desc: Brief text description
 - due: Due date
 - tags: Optional list of context tags
 - tstamp: Time stamp of when item was entered
 - tfinish: Optional time stamp of when item was marked done
 - tclock: Optional number of minutes spent on an item
 - note: Optional note with further details

The time stamp indicates when the entry was logged; the date indicates
when the event actually happened.  If I fall asleep before logging the
evening's happenings, I may enter some things from the previous night in
the morning, so the date and the time stamp do not always agree.

When an item is actually logged in real-time, marking it done (and setting
the `tfinish` field) is a good way of recording the time taken.  When the
log is updated only after the relevant time, the `tclock` field indicates an
estimate of how much time was taken.

## Collection file

Collections consists of log-like entries that do not actually correspond
to log events.  These might be URLs that I want to revisit, books finished,
quotes, etc.  They typically do not have time finished or clock information,
but otherwise look much like log file entries.

## To do file

The todo file has two subsections: `scheduled` and `todo`.

Under `scheduled`, there are rules for future tasks that have not yet
been scheduled.  The simplest of these are task records with future
dates.  These are moved to the main task list once the indicated date
arrives.  Scheduled tasks with a `repeat` field are copied to the main
task list, then re-scheduled for `repeat` days after the original.

Under `todo`, there are active tasks.  I try to keep the `todo` list
fairly short.  For a more complete list of tasks and long-range plans,
I keep a separate text file that I consult with regularly (but not
with the same frequency as the main `todo`).

The task entries look like log file entries, but without the time stamps
or clock fields.
