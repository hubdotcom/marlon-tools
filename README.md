# marlon-tools
Automatically exported from code.google.com/p/marlon-tools

**dnsproxy**

A simple DNS proxy server, support wilcard hosts, IPv6, cache.

Usage:

```
1. Edit /etc/hosts, add:
127.0.0.1 *.local
-2404:6800:8005::62 *.blogspot.com

2. startup dnsproxy (here using Google DNS server as delegating server):
$ sudo python dnsproxy.py -s 8.8.8.8

3. Then set system dns server as 127.0.0.1, you can verify it by dig:
$ dig test.local
The result should contain 127.0.0.1.

```
