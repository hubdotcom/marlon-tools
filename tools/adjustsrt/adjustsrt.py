#!/usr/bin/env python
# coding: utf-8
from optparse import OptionParser

import re
import sys
import time

def main():
    parser = OptionParser(usage='%prog -d delay [src_srt] [dest_srt]', description=u'调整srt字幕文件的延时')
    parser.add_option('-d', '--delay', dest='delay', metavar='DELAY', help=u'延时时间(秒),负数表示提前')
    opts, args = parser.parse_args(sys.argv[1:])

    if not opts.delay or len(args) > 2:
        parser.print_help()
        sys.exit(1)
    fin, fout = sys.stdin, sys.stdout
    try:
        if len(args) >= 1:
            fin = open(args[0], 'r')
        if len(args) == 2:
            fout = open(args[1], 'w')
        delay(fin, fout, float(opts.delay))
    except IOError as e:
        print >> sys.stderr, u'找不到文件: %s' % e.filename
        sys.exit(2)
    finally:
        fin.close()
        fout.close()

class Time(object):
    M_SEC = 1000
    M_MIN = 60 * 1000
    M_HOUR = 3600 * 1000
    def __init__(self, hours=0, mins=0, secs=0, millis=0):
        self.millis = hours*self.M_HOUR + mins*self.M_MIN + secs*self.M_SEC + millis

    def __add__(self, secs):
        millis = int(secs * self.M_SEC)
        return Time(millis=self.millis + millis)

    def __sub__(self, secs):
        return self.__add__(-secs)

    def __str__(self):
        secs, millis = self.millis/1000, self.millis%1000
        mins, secs = secs/60, secs%60
        hours, mins = mins/60, mins%60
        return '%02d:%02d:%02d,%03d' % (hours, mins, secs, millis)

RE_TIME = re.compile(r'^(\d{1,2}):(\d{1,2}):(\d{1,2}),(\d{1,3})')
def parse_time(time_str):
    m = RE_TIME.match(time_str)
    if m:
        return Time(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None

RE_TIME_LINE = re.compile(r'^(\d{1,2}:\d{1,2}:\d{1,2},\d{1,3}) --> (\d{1,2}:\d{1,2}:\d{1,2},\d{1,3})(\s*)$')

def delay(fin, fout, delay):
    for line in fin.readlines():
        m = RE_TIME_LINE.match(line)
        if m:
            s_time = parse_time(m.group(1)) + delay
            e_time = parse_time(m.group(2)) + delay
            fout.write('%s --> %s%s' % (s_time, e_time, m.group(3)))
        else:
            fout.write(line)

if __name__ == '__main__':
    main()

