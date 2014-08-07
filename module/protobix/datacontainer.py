import simplejson
import time

from senderprotocol import SenderProtocol

class DataContainer(SenderProtocol):

    def __init__(self, data_type=None, zbx_host="", zbx_port=10051):
        super( DataContainer, self).__init__()
        self.request = "sender data"
        self.zbx_host = zbx_host
        self.zbx_port = zbx_port
        self.items_list = []
        self.data_type = data_type

    def set_type(self, data_type):
        if data_type == "lld" or data_type == "items":
            self.data_type = data_type

    def add_item(self, host, key, value, clock=int(time.time())/60*60):
        if self.data_type == "items":
            item = { "host": host, "key": key,
                     "value": value, "clock": clock}
        elif self.data_type == "lld":
            item = { "host": host, "key": key, "clock": clock,
                     "value": simplejson.dumps({"data":value}) }
        self.items_list.append(item)

    def add(self, data):
        for host in data:
            for key in data[host]:
                if not data[host][key] == []:
                    self.add_item( host, key, data[host][key])

    def get_items_list(self):
        return self.items_list
