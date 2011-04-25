#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from SocketServer import BaseRequestHandler, ThreadingUDPServer
from cStringIO import StringIO
import socket
import struct

DNS_FLAG_QR = 0x8000
DNS_FLAG_RD = 0x0100
DNS_FLAG_RA = 0x0080

DNS_TYPE_A = 1
DNS_TYPE_AAAA = 28
DNS_CLASS_IN = 1

'''
一个简单的DNS代理服务器，支持域名通配符匹配，缓存。

author: marlonyao<yaolei135@gmail.com>
'''
class DNSMessageHeader(object):
    def __init__(self, id, flag, qd_count, an_count, ns_count, ar_count):
        self.id = id
        self.flag = flag
        self.qd_count = qd_count
        self.an_count = an_count
        self.ns_count = ns_count
        self.ar_count = ar_count

    @staticmethod
    def parse(message):
        id, flag = struct.unpack('!HH', message.read(4))
        qd_count, an_count, ns_count, ar_count = struct.unpack('!HHHH', message.read(8))
        return DNSMessageHeader(id, flag, qd_count, an_count, ns_count, ar_count)

    def serialize(self, message, memoize=None):
        message.write(struct.pack('!HHHHHH', self.id, self.flag,
                       self.qd_count, self.an_count, self.ns_count, self.ar_count))

    def __str__(self):
        return 'id: %s, flag: %s, qd_count: %s, an_count: %s, ns_count: %s, ar_count: %s' % (
            self.id, self.flag, self.qd_count, self.an_count, self.ns_count, self.ar_count
        )

class DNSMessageQuestion(object):
    def __init__(self, qname, qtype, qclass):
        self.qname = qname
        self.qtype = qtype
        self.qclass = qclass

    @staticmethod
    def parse(message):
        qname = parse_domain_name(message)
        qtype, qclass = struct.unpack('!HH', message.read(4))
        return DNSMessageQuestion(qname, qtype, qclass)

    def serialize(self, message, memoize):
        unparse_domain_name(self.qname, message, memoize)
        message.write(struct.pack('!HH', self.qtype, self.qclass))

    def __str__(self):
        return 'qname: %s, qtype: %s, qclass: %s' % (self.qname, self.qtype, self.qclass)

    def __repr__(self):
        return str(self)

class DNSMessageRecord(object):
    def __init__(self, name, type_, class_, ttl, rdata):
        self.name = name
        self.type_ = type_
        self.class_ = class_
        self.ttl = ttl
        self.rdata = rdata

    @staticmethod
    def parse(message):
        name = parse_domain_name(message)
        type_, class_, ttl, rd_len = struct.unpack('!HHIH', message.read(10))
        return DNSMessageRecord(name, type_, class_, ttl, message.read(rd_len))

    def serialize(self, message, memoize):
        unparse_domain_name(self.name, message, memoize)
        message.write(struct.pack('!HHIH%ss'%len(self.rdata),
                    self.type_, self.class_, self.ttl,
                    len(self.rdata), self.rdata,
                ))

    def __str__(self):
        return "name: %s, type: %s, class: %s, ttl: %s, rdata: %s" % (
            self.name, self.type_, self.class_, self.ttl, self.rdata
        )

    def __repr__(self):
        return str(self)

class DNSMessage(object):
    def __init__(self, header, questions=None, answers=None, authorities=None, additionals=None):
        self.header = header
        self.questions = questions or []
        self.answers = answers or []
        self.authorities = authorities or []
        self.additionals = additionals or []

    @staticmethod
    def parse(data):
        message = StringIO(data)
        header = DNSMessageHeader.parse(message)
        questions = []
        for i in range(0, header.qd_count):
            quest = DNSMessageQuestion.parse(message)
            questions.append(quest)
        answers = []
        for i in range(0, header.an_count):
            answer = DNSMessageRecord.parse(message)
            answers.append(answer)
        authorities = []
        for i in range(0, header.ns_count):
            authority = DNSMessageRecord.parse(message)
            authorities.append(authority)
        additionals = []
        for i in range(0, header.ar_count):
            additional = DNSMessageRecord.parse(message)
            additionals.append(additional)
        return DNSMessage(header, questions, answers, authorities, additionals)

    def serialize(self):
        'serialize to network bytes, not considering name compression'
        message = StringIO()
        memoize = {}
        self.header.serialize(message, memoize)
        for s in self.questions:
            s.serialize(message, memoize)
        for s in self.answers:
            s.serialize(message, memoize)
        for s in self.authorities:
            s.serialize(message, memoize)
        for s in self.additionals:
            s.serialize(message, memoize)
        return message.getvalue()

    def __str__(self):
        return 'header: %s\n' % self.header +\
               'questions: %s\n' % self.questions +\
               'answers: %s\n' % self.answers +\
               'authorities: %s\n' % self.authorities +\
               'additionals: %s\n' % self.additionals

    def __repr__(self):
        return str(self)

def _parse_domain_labels(message):
    labels = []
    len = ord(message.read(1))
    while len > 0:
        if len >= 64:   # domain name compression
            len = len & 0x3f
            offset = (len << 8) + ord(message.read(1))
            mesg = StringIO(message.getvalue())
            mesg.seek(offset)
            labels.extend(_parse_domain_labels(mesg))
            return labels
        else:
            labels.append(message.read(len))
            len = ord(message.read(1))
    return labels
def parse_domain_name(message):
    return '.'.join(_parse_domain_labels(message))

def unparse_domain_name(name, message, memoize):
    labels = name.split('.')
    for i, label in enumerate(labels):
        qname = '.'.join(labels[i:])
        if qname in memoize:
            offset = (memoize[qname] & 0x3fff) + 0xc000
            message.write(struct.pack('!H', offset))
            break
        else:
            memoize[qname] = message.tell()
            #print 'add to memoize: %s, %s' % (qname, message.tell())
            message.write(struct.pack('!B%ss' % len(label), len(label), label))
    else:
        # write last ending zero
        message.write('\x00')

def addr_p2n(addr):
    try:
        return socket.inet_pton(socket.AF_INET, addr)
    except:
        return socket.inet_pton(socket.AF_INET6, addr)

class DNSProxyHandler(BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        req = DNSMessage.parse(data)

        quest = req.questions[0]
        qname = quest.qname
        if (quest.qtype == DNS_TYPE_A or quest.qtype == DNS_TYPE_AAAA) \
                and (quest.qclass == DNS_CLASS_IN):
            for packed_ip, host in self.server.host_lines:
                if qname.endswith(host):
                    resp = DNSMessage(req.header, req.questions)
                    resp.header.flag = DNS_FLAG_QR|DNS_FLAG_RD|DNS_FLAG_RA
                    resp.header.an_count = 1
                    resp.answers.append(DNSMessageRecord(quest.qname,
                            DNS_TYPE_A if len(packed_ip) == 4 else DNS_TYPE_AAAA,
                            DNS_CLASS_IN, 2000, packed_ip))
                    rspdata = resp.serialize()
                    sock.sendto(rspdata, self.client_address)
                    return
            # lookup cache
            cache = self.server.cache
            if cache.get(qname):
                answers = cache[qname]
                resp = DNSMessage(req.header, req.questions)
                resp.header.flag = DNS_FLAG_QR|DNS_FLAG_RD|DNS_FLAG_RA
                resp.answers = answers
                resp.header.an_count = len(answers)
                rspdata = resp.serialize()
                sock.sendto(rspdata, self.client_address)
                return
            rspdata = self._getResponse(data)
            resp = DNSMessage.parse(rspdata)
            answers = [ a for a in resp.answers if a.type_ in (DNS_TYPE_A, DNS_TYPE_AAAA) and a.class_ == DNS_CLASS_IN ]
            if answers:
                cache[qname] = answers
            sock.sendto(rspdata, self.client_address)
        else:
            rspdata = self._getResponse(data)
            resp = DNSMessage.parse(rspdata)
            sock.sendto(rspdata, self.client_address)

    def _getResponse(self, data):
        "Send client's DNS request (data) to remote DNS server, and return its response."
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # socket for the remote DNS server
        sock.connect((self.server.dns_server, 53))
        sock.sendall(data)
        sock.settimeout(45)
        rspdata = sock.recv(65535)
        sock.close()
        return rspdata


def load_hosts(hosts_file):
    'load hosts config, only extract config line contains wildcard domain name'
    def wildcard_line(line):
        parts = line.strip().split()[:2]
        if len(parts) < 2: return False
        if not parts[1].startswith('*'): return False
        try:
            packed_ip = addr_p2n(parts[0])
            return packed_ip, parts[1][1:]
        except:
            return None
    with open(hosts_file) as hosts_in:
        hostlines = []
        for line in hosts_in:
            hostline = wildcard_line(line)
            if hostline:
                hostlines.append(hostline)
        return hostlines

class DNSProxyServer(ThreadingUDPServer):
    def __init__(self, dns_server, host='127.0.0.1', port=53, hosts_file='/etc/hosts'):
        self.dns_server = dns_server
        self.hosts_file = hosts_file
        self.host_lines = load_hosts(hosts_file)
        self.cache = {}
        ThreadingUDPServer.__init__(self, (host, port), DNSProxyHandler)

def main():
    import optparse, sys
    parser = optparse.OptionParser()
    parser.add_option('-f', '--hosts-file', dest='hosts_file', metavar='<file>', default='/etc/hosts', help='specify hosts file, default /etc/hosts')
    parser.add_option('-H', '--host', dest='host', default='127.0.0.1', help='specify the address to listen on')
    parser.add_option('-p', '--port', dest='port', default=53, type='int', help='specify the port to listen on')
    parser.add_option('-s', '--server', dest='dns_server', metavar='SERVER', help='specify the delegating dns server')

    opts, args = parser.parse_args()
    if not opts.dns_server:
        parser.print_help()
        sys.exit(1)
    dnsserver = DNSProxyServer(opts.dns_server, host=opts.host, port=opts.port, hosts_file=opts.hosts_file)
    dnsserver.serve_forever()

if __name__ == '__main__':
    main()
