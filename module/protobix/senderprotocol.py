import logging
import re
import simplejson
import socket
import struct
import time

from senderexception import SenderException

ZBX_HDR = "ZBXD\1"
ZBX_HDR_SIZE = 13
ZBX_RESP_REGEX = r'Processed (\d+) Failed (\d+) Total (\d+) Seconds spent (\d\.\d+)'
ZBX_DBG_SEND_RESULT = "DBG - Send result [%s] for [%s %s %s]"

def recv_all(sock):
    buf = ''
    while len(buf)<ZBX_HDR_SIZE:
        chunk = sock.recv(ZBX_HDR_SIZE-len(buf))
        if not chunk:
            return buf
        buf += chunk
    return buf

class SenderProtocol(object):

    def __init__(self, zbx_host="", zbx_port=10051):
        self.debug = False
        self.verbosity = False
        self.dryrun = False
        self.request = ""
        self.zbx_host = zbx_host
        self.zbx_port = zbx_port
        self.data_container = ""

    def set_host(self, zbx_host):
        self.zbx_host = zbx_host

    def set_port(self, zbx_port):
        self.zbx_port = zbx_port

    def set_verbosity(self, verbosity):
        self.verbosity = verbosity

    def set_debug(self, debug):
        self.debug = debug

    def set_dryrun(self, dryrun):
        self.dryrun = dryrun

    def __repr__(self):
        return simplejson.dumps({ "data": ("%r" % self.data_container),
                                  "request": self.request,
                                  "clock": int(time.time()) })

    def send_to_zabbix(self, data):
        data_len =  struct.pack('<Q', len(data))
        packet = ZBX_HDR + data_len + data

        try:
            zbx_sock = socket.socket()
            zbx_sock.connect((self.zbx_host, int(self.zbx_port)))
            zbx_sock.sendall(packet)
        except (socket.gaierror, socket.error) as e:
            zbx_sock.close()
            raise SenderException(e[1])
        else:
            try:
                zbx_srv_resp_hdr = recv_all(zbx_sock)
                zbx_srv_resp_body_len = struct.unpack('<Q', zbx_srv_resp_hdr[5:])[0]
                zbx_srv_resp_body = zbx_sock.recv(zbx_srv_resp_body_len)
                zbx_sock.close()
            except:
                zbx_sock.close()
                if not zbx_srv_resp_hdr.startswith(ZBX_HDR) or len(zbx_srv_resp_hdr) != ZBX_HDR_SIZE:
                    raise SenderException("Wrong zabbix response")
                else:
                    raise SenderException("Error while sending data to Zabbix")

        return simplejson.loads(zbx_srv_resp_body)

    def send(self, container):
        if self.debug:
            zbx_answer = self.single_send(container)
        else:
            zbx_answer = self.bulk_send(container)
        return zbx_answer

    def bulk_send(self, container):
        self.data_container = container
        data = simplejson.dumps({ "data": self.data_container.get_items_list(),
                                  "request": self.request,
                                  "clock": int(time.time()) })
        zbx_answer = self.send_to_zabbix(data)
        if self.verbosity:
            print zbx_answer.get('info')
        return zbx_answer

    def single_send(self, container):
        self.data_container = container
        for item in self.data_container.get_items_list():
            data = simplejson.dumps({ "data": [ item ],
                                      "request": self.request,
                                      "clock": int(time.time()) })
            result = '-'
            zbx_answer = 0
            if not self.dryrun:
                zbx_answer = self.send_to_zabbix(data)
                regex = re.match( ZBX_RESP_REGEX, zbx_answer.get('info'))
                result = regex.group(1)

            if self.debug:
                print (ZBX_DBG_SEND_RESULT % (result,
                                              item["host"],
                                              item["key"],
                                              item["value"]))
        return zbx_answer
