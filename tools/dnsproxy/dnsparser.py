# coding: utf-8
from cStringIO import StringIO
import struct

DNS_FLAG_QR = 0x8000
DNS_FLAG_RD = 0x0100
DNS_FLAG_RA = 0x0080

DNS_TYPE_A = 1
DNS_TYPE_AAAA = 28
DNS_CLASS_IN = 1

'''
一个简单的DNS解析器。

解析：
msg = DNSMessage.parse(message data)

序列化：
data = msg.serialize()


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

