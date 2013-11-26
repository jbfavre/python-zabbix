import simplejson
import struct
import socket

ZBX_HDR = "ZBXD\1"
ZBX_HDR_SIZE = 13

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

    def __repr__(self):
        return simplejson.dumps({ "data": ("%r" % self.data_container),
                                  "request": self.request })

    def send_to_zabbix(self, data):
        data_len =  struct.pack('<Q', len(data))
        packet = ZBX_HDR + data_len + data
        zbx_srv_resp_hdr = ""

        try:
            zbx_sock = socket.socket()
            zbx_sock.connect((self.zbx_host, int(self.zbx_port)))
            zbx_sock.sendall(packet)
        except:
            print("Error while connecting to Zabbix server [%s:%d]"%(self.zbx_host, self.zbx_port))
            return False

        try:
            zbx_srv_resp_hdr = recv_all(zbx_sock)
            zbx_srv_resp_body_len = struct.unpack('<Q', zbx_srv_resp_hdr[5:])[0]
            zbx_srv_resp_body = zbx_sock.recv(zbx_srv_resp_body_len)
            zbx_sock.close()
        except:
            if not zbx_srv_resp_hdr.startswith(ZBX_HDR) or len(zbx_srv_resp_hdr) != ZBX_HDR_SIZE:
                print("Wrong zabbix response")
            else:
                print("Error while sending data to Zabbix")
            return False

        return simplejson.loads(zbx_srv_resp_body)

    def send(self, container):
        if self.debug:
            self.single_send(container)
        else:
            self.bulk_send(container)

    def bulk_send(self, container):
        self.data_container = container
        data = simplejson.dumps({ "data": self.data_container.get_items_list(),
                                  "request": self.request })
        zbx_answer = self.send_to_zabbix(data)
        if self.verbosity:
            print zbx_answer.get('info')

    def single_send(self, container):
        self.data_container = container

        for item in self.data_container.get_items_list():

            data = simplejson.dumps({ "data": [ item ],
                                      "request": self.request })
            zbx_answer = self.send_to_zabbix(data)

            if self.debug:
                if self.verbosity:
                    print ("%s - %s - %s - %s - %s" % (item["host"],
                                                       item["key"],
                                                       data,
                                                       item["value"],
                                                       zbx_answer.get('info')))
                else:
                    print ("%s - %s - %s" % (item["host"],
                                             item["key"],
                                             zbx_answer.get('info')))
