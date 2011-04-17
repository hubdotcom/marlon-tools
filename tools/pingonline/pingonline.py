#!/usr/bin/env python
# coding: utf-8
import cookielib
import optparse
import re
import sys
import urllib
import urllib2

RE_TOKEN = re.compile(r'<input type="hidden" name="token" value="(\w+)"')
RE_IPOUT = re.compile(r'<pre>(.*?)<br />', re.DOTALL)
RE_IPADDR=re.compile(r'\(([\w.:]*)\)')

PING_URL = 'http://www.subnetonline.com/pages/network-tools/online-ping-ipv4.php'
PING6_URL = 'http://www.subnetonline.com/pages/ipv6-network-tools/online-ipv6-ping.php'

def ping(host, v6=False, count=4, ttl=255, size=32, only_ip=False):
    url = PING_URL
    if v6:
        url = PING6_URL
    cj = cookielib.LWPCookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    urllib2.install_opener(opener)
    resp = urllib2.urlopen(url)
    content = resp.read()
    #print content
    # get token
    m = RE_TOKEN.search(content)
    if m:
        token = m.group(1)
    else:
        print >> sys.stderr, 'error: cannot find token'
        return None
    # post data
    data = {
        'host': host,
        'token': token,
        'count': str(count),
        'ttl': str(ttl),
        'size': str(size),
    }
    resp = urllib2.urlopen(url, data=urllib.urlencode(data))
    content = resp.read()
    #print content
    m = RE_IPOUT.search(content)
    if m:
        content = m.group(1)[:-1]          # remove the last '\n'
    else:
        print >> sys.stderr, 'error: cannot find output'
        return None
    if not only_ip:
        return content
    else:
        m = RE_IPADDR.search(content)
        if m:
            ip = m.group(1)
            return ip
        else:
            print >> sys.stderr, 'error: cannot find ip address'
            return None


def main():
    parser = optparse.OptionParser(usage=u'%prog [-hp6] [-c count] [-t ttl] [-s packetsize] destination')
    parser.add_option('-c', dest='count', type='int', help='Stop after sending count ECHO_REQUEST packets.', default=4)
    parser.add_option('-t', dest='ttl', type='int', help='Set the IP Time to Live.', default=255)
    parser.add_option('-s', dest='packetsize', type='int', help='Specifies the number of data bytes to be sent.', default=32)
    parser.add_option('-6', dest='ipv6', action='store_true', help='Specifies whether use IPv6', default=False)
    parser.add_option('-p', dest='only_ip', action='store_true', default=False, help='only output ipv6 address, can be used lookup ipv6 address according by host.')

    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    res = ping(args[0], count=opts.count, ttl=opts.ttl, size=opts.packetsize, only_ip=opts.only_ip, v6=opts.ipv6)
    if res:
        print res
    elif res is None:
        sys.exit(2)
    else:
        print >> sys.stderr, '%s not reachable' % args[0]
        sys.exit(3)

if __name__ == '__main__':
    main()

