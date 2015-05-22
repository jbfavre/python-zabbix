#!/usr/bin/env python

''' Copyright (c) 2013 Jean Baptiste Favre.
    Sample script for Zabbix integration with Supervisord.
'''
import optparse
import platform
import protobix

import ConfigParser
import simplejson
import os

################################################################################
# Embedded FastCGI client
################################################################################

# Copyright (c) 2006 Allan Saddi <allan@saddi.com>
# Copyright (c) 2011 Vladimir Rusinov <vladimir@greenmice.info>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# $Id$

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision$'

import select  # @UnresolvedImport
import struct
import socket
import errno
import types

__all__ = ['FCGIApp']

# Constants from the spec.
FCGI_LISTENSOCK_FILENO = 0

FCGI_HEADER_LEN = 8

FCGI_VERSION_1 = 1

FCGI_BEGIN_REQUEST = 1
FCGI_ABORT_REQUEST = 2
FCGI_END_REQUEST = 3
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_STDOUT = 6
FCGI_STDERR = 7
FCGI_DATA = 8
FCGI_GET_VALUES = 9
FCGI_GET_VALUES_RESULT = 10
FCGI_UNKNOWN_TYPE = 11
FCGI_MAXTYPE = FCGI_UNKNOWN_TYPE

FCGI_NULL_REQUEST_ID = 0

FCGI_KEEP_CONN = 1

FCGI_RESPONDER = 1
FCGI_AUTHORIZER = 2
FCGI_FILTER = 3

FCGI_REQUEST_COMPLETE = 0
FCGI_CANT_MPX_CONN = 1
FCGI_OVERLOADED = 2
FCGI_UNKNOWN_ROLE = 3

FCGI_MAX_CONNS = 'FCGI_MAX_CONNS'
FCGI_MAX_REQS = 'FCGI_MAX_REQS'
FCGI_MPXS_CONNS = 'FCGI_MPXS_CONNS'

FCGI_Header = '!BBHHBx'
FCGI_BeginRequestBody = '!HB5x'
FCGI_EndRequestBody = '!LB3x'
FCGI_UnknownTypeBody = '!B7x'

FCGI_BeginRequestBody_LEN = struct.calcsize(FCGI_BeginRequestBody)
FCGI_EndRequestBody_LEN = struct.calcsize(FCGI_EndRequestBody)
FCGI_UnknownTypeBody_LEN = struct.calcsize(FCGI_UnknownTypeBody)

if __debug__:
    import time

    # Set non-zero to write debug output to a file.
    DEBUG = 0
    DEBUGLOG = '/tmp/fcgi_app.log'

    def _debug(level, msg):
        # pylint: disable=W0702
        if DEBUG < level:
            return

        try:
            f = open(DEBUGLOG, 'a')
            f.write('%sfcgi: %s\n' % (time.ctime()[4:-4], msg))
            f.close()
        except:
            pass


def decode_pair(s, pos=0):
    """
    Decodes a name/value pair.

    The number of bytes decoded as well as the name/value pair
    are returned.
    """
    nameLength = ord(s[pos])
    if nameLength & 128:
        nameLength = struct.unpack('!L', s[pos:pos + 4])[0] & 0x7fffffff
        pos += 4
    else:
        pos += 1

    valueLength = ord(s[pos])
    if valueLength & 128:
        valueLength = struct.unpack('!L', s[pos:pos + 4])[0] & 0x7fffffff
        pos += 4
    else:
        pos += 1

    name = s[pos:pos + nameLength]
    pos += nameLength
    value = s[pos:pos + valueLength]
    pos += valueLength

    return (pos, (name, value))


def encode_pair(name, value):
    """
    Encodes a name/value pair.

    The encoded string is returned.
    """
    nameLength = len(name)
    if nameLength < 128:
        s = chr(nameLength)
    else:
        s = struct.pack('!L', nameLength | 0x80000000L)

    valueLength = len(value)
    if valueLength < 128:
        s += chr(valueLength)
    else:
        s += struct.pack('!L', valueLength | 0x80000000L)

    return s + name + value


class Record(object):
    """
    A FastCGI Record.

    Used for encoding/decoding records.
    """

    def __init__(self, typ=FCGI_UNKNOWN_TYPE, requestId=FCGI_NULL_REQUEST_ID):
        self.version = FCGI_VERSION_1
        self.type = typ
        self.requestId = requestId
        self.contentLength = 0
        self.paddingLength = 0
        self.contentData = ''

    def _recvall(sock, length):
        """
        Attempts to receive length bytes from a socket, blocking if necessary.
        (Socket may be blocking or non-blocking.)
        """
        dataList = []
        recvLen = 0
        while length:
            try:
                data = sock.recv(length)
            except socket.error, e:
                if e[0] == errno.EAGAIN:
                    select.select([sock], [], [])
                    continue
                else:
                    raise
            if not data:  # EOF
                break
            dataList.append(data)
            dataLen = len(data)
            recvLen += dataLen
            length -= dataLen
        return ''.join(dataList), recvLen
    _recvall = staticmethod(_recvall)

    def read(self, sock):
        """Read and decode a Record from a socket."""
        try:
            header, length = self._recvall(sock, FCGI_HEADER_LEN)
        except:
            raise EOFError

        if length < FCGI_HEADER_LEN:
            raise EOFError

        self.version, self.type, self.requestId, self.contentLength, \
                      self.paddingLength = struct.unpack(FCGI_Header, header)

        if __debug__:
            _debug(9, 'read: fd = %d, type = %d, requestId = %d, '
                             'contentLength = %d' %
                             (sock.fileno(), self.type, self.requestId,
                              self.contentLength))

        if self.contentLength:
            try:
                self.contentData, length = self._recvall(sock,
                                                         self.contentLength)
            except:
                raise EOFError

            if length < self.contentLength:
                raise EOFError

        if self.paddingLength:
            try:
                self._recvall(sock, self.paddingLength)
            except:
                raise EOFError

    def _sendall(sock, data):
        """
        Writes data to a socket and does not return until all the data is sent.
        """
        length = len(data)
        while length:
            try:
                sent = sock.send(data)
            except socket.error, e:
                if e[0] == errno.EAGAIN:
                    select.select([], [sock], [])
                    continue
                else:
                    raise
            data = data[sent:]
            length -= sent
    _sendall = staticmethod(_sendall)

    def write(self, sock):
        """Encode and write a Record to a socket."""
        self.paddingLength = - self.contentLength & 7

        if __debug__:
            _debug(9, 'write: fd = %d, type = %d, requestId = %d, '
                             'contentLength = %d' %
                             (sock.fileno(), self.type, self.requestId,
                              self.contentLength))

        header = struct.pack(FCGI_Header, self.version, self.type,
                             self.requestId, self.contentLength,
                             self.paddingLength)
        self._sendall(sock, header)
        if self.contentLength:
            self._sendall(sock, self.contentData)
        if self.paddingLength:
            self._sendall(sock, '\x00' * self.paddingLength)


class FCGIApp(object):

    def __init__(self, connect=None, host=None, port=None, filterEnviron=True):
        if host is not None:
            assert port is not None
            connect = (host, port)

        self._connect = connect
        self._filterEnviron = filterEnviron

    def __call__(self, environ, start_response=None):
        # For sanity's sake, we don't care about FCGI_MPXS_CONN
        # (connection multiplexing). For every request, we obtain a new
        # transport socket, perform the request, then discard the socket.
        # This is, I believe, how mod_fastcgi does things...

        sock = self._getConnection()

        # Since this is going to be the only request on this connection,
        # set the request ID to 1.
        requestId = 1

        # Begin the request
        rec = Record(FCGI_BEGIN_REQUEST, requestId)
        rec.contentData = struct.pack(FCGI_BeginRequestBody, FCGI_RESPONDER, 0)
        rec.contentLength = FCGI_BeginRequestBody_LEN
        rec.write(sock)

        # Filter WSGI environ and send it as FCGI_PARAMS
        if self._filterEnviron:
            params = self._defaultFilterEnviron(environ)
        else:
            params = self._lightFilterEnviron(environ)
        # TODO: Anything not from environ that needs to be sent also?
        self._fcgiParams(sock, requestId, params)
        self._fcgiParams(sock, requestId, {})

        # Transfer wsgi.input to FCGI_STDIN
        #content_length = int(environ.get('CONTENT_LENGTH') or 0)
        s = ''
        while True:
            #chunk_size = min(content_length, 4096)
            #s = environ['wsgi.input'].read(chunk_size)
            #content_length -= len(s)
            rec = Record(FCGI_STDIN, requestId)
            rec.contentData = s
            rec.contentLength = len(s)
            rec.write(sock)
            if not s:
                break

        # Empty FCGI_DATA stream
        rec = Record(FCGI_DATA, requestId)
        rec.write(sock)

        # Main loop. Process FCGI_STDOUT, FCGI_STDERR, FCGI_END_REQUEST
        # records from the application.
        result = []
        err = ''
        while True:
            inrec = Record()
            inrec.read(sock)
            if inrec.type == FCGI_STDOUT:
                if inrec.contentData:
                    result.append(inrec.contentData)
                else:
                    # TODO: Should probably be pedantic and no longer
                    # accept FCGI_STDOUT records?"
                    pass
            elif inrec.type == FCGI_STDERR:
                # Simply forward to wsgi.errors
                err += inrec.contentData
                #environ['wsgi.errors'].write(inrec.contentData)
            elif inrec.type == FCGI_END_REQUEST:
                # TODO: Process appStatus/protocolStatus fields?
                break

        # Done with this transport socket, close it. (FCGI_KEEP_CONN was not
        # set in the FCGI_BEGIN_REQUEST record we sent above. So the
        # application is expected to do the same.)
        sock.close()

        result = ''.join(result)

        # Parse response headers from FCGI_STDOUT
        status = '200 OK'
        headers = []
        pos = 0
        while True:
            eolpos = result.find('\n', pos)
            if eolpos < 0:
                break
            line = result[pos:eolpos - 1]
            pos = eolpos + 1

            # strip in case of CR. NB: This will also strip other
            # whitespace...
            line = line.strip()

            # Empty line signifies end of headers
            if not line:
                break

            # TODO: Better error handling
            header, value = line.split(':', 1)
            header = header.strip().lower()
            value = value.strip()

            if header == 'status':
                # Special handling of Status header
                status = value
                if status.find(' ') < 0:
                    # Append a dummy reason phrase if one was not provided
                    status += ' FCGIApp'
            else:
                headers.append((header, value))

        result = result[pos:]

        # Set WSGI status, headers, and return result.
        #start_response(status, headers)
        #return [result]

        return status, headers, result, err

    def _getConnection(self):
        if self._connect is not None:
            # The simple case. Create a socket and connect to the
            # application.
            if isinstance(self._connect, types.StringTypes):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(self._connect)
            elif hasattr(socket, 'create_connection'):
                sock = socket.create_connection(self._connect)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(self._connect)
            return sock

        # To be done when I have more time...
        raise NotImplementedError(
            'Launching and managing FastCGI programs not yet implemented')

    def _fcgiGetValues(self, sock, vars):  # @ReservedAssignment
        # Construct FCGI_GET_VALUES record
        outrec = Record(FCGI_GET_VALUES)
        data = []
        for name in vars:
            data.append(encode_pair(name, ''))
        data = ''.join(data)
        outrec.contentData = data
        outrec.contentLength = len(data)
        outrec.write(sock)

        # Await response
        inrec = Record()
        inrec.read(sock)
        result = {}
        if inrec.type == FCGI_GET_VALUES_RESULT:
            pos = 0
            while pos < inrec.contentLength:
                pos, (name, value) = decode_pair(inrec.contentData, pos)
                result[name] = value
        return result

    def _fcgiParams(self, sock, requestId, params):
        #print params
        rec = Record(FCGI_PARAMS, requestId)
        data = []
        for name, value in params.items():
            data.append(encode_pair(name, value))
        data = ''.join(data)
        rec.contentData = data
        rec.contentLength = len(data)
        rec.write(sock)

    _environPrefixes = ['SERVER_', 'HTTP_', 'REQUEST_', 'REMOTE_', 'PATH_',
                        'CONTENT_', 'DOCUMENT_', 'SCRIPT_']
    _environCopies = ['SCRIPT_NAME', 'QUERY_STRING', 'AUTH_TYPE']
    _environRenames = {}

    def _defaultFilterEnviron(self, environ):
        result = {}
        for n in environ.keys():
            for p in self._environPrefixes:
                if n.startswith(p):
                    result[n] = environ[n]
            if n in self._environCopies:
                result[n] = environ[n]
            if n in self._environRenames:
                result[self._environRenames[n]] = environ[n]

        return result

    def _lightFilterEnviron(self, environ):
        result = {}
        for n in environ.keys():
            if n.upper() == n:
                result[n] = environ[n]
        return result


################################################################################
# PHP-FPM plugin
################################################################################

__version__ = '0.0.1'
ZBX_CONN_ERR = 'ERR - unable to send data to Zabbix [%s]'

PHP_POOL_CONFIG_KEYS = [
  'pm.start_servers',
  'pm.min_spare_servers',
  'pm.max_children',
  'pm.max_spare_servers'
]

PHP_POOL_STATUS_KEYS = [
  'active processes',
  'accepted conn',
  'listen queue',
  'start since',
  'idle processes',
  'start time',
  'slow requests',
  'max active processes',
  'max children reached',
  'max listen queue',
  'total processes',
  'listen queue len'
]

class PhpFpm(object):
  
  def get_pool_page(self, connect, url):
    """ load fastcgi page """
    fcgi = FCGIApp(connect=connect)
    env = {
     'SCRIPT_FILENAME': url,
     'QUERY_STRING': 'json',
     'REQUEST_METHOD': 'GET',
     'SCRIPT_NAME': url,
     'REQUEST_URI': url,
     'GATEWAY_INTERFACE': 'CGI/1.1',
     'SERVER_SOFTWARE': 'protobix',
     'REDIRECT_STATUS': '200',
     'CONTENT_TYPE': '',
     'CONTENT_LENGTH': '0',
     'DOCUMENT_ROOT': '/',
     'DOCUMENT_ROOT': '/var/www/',
     'REMOTE_ADDR': '127.0.0.1',
     'REMOTE_PORT': '123',
     'SERVER_ADDR': 'monitoring',
     'SERVER_PORT': '1024',
     'SERVER_NAME': 'monitoring'}
    ret = fcgi(env, 0)
    return ret

  def get_metrics(self):
    data = {}
    pool_list = self.get_pools_config()
    for pool in pool_list:
      pool_config = pool_list[pool]
      for config_key in PHP_POOL_CONFIG_KEYS:
        zbx_key = 'php-fpm.pool.config[{0},{1}]'
        zbx_key = zbx_key.format(pool, config_key)
        data[zbx_key] = pool_config[config_key]
      try:
        code, headers, out, err = self.get_pool_page( pool_config['listen'],
                                                      pool_config['ping.path'])
        code_only = int(code.split()[0])
        zbx_key = 'php-fpm.pool.ping[{0}]'
        zbx_key = zbx_key.format(pool)
        data[zbx_key] = 0
        if code_only == 200:
          data[zbx_key] = 1
        print out
      except:
        zbx_key = 'php-fpm.pool.ping[{0}]'
        zbx_key = zbx_key.format(pool)
        data[zbx_key] = 0
        pass
      try:
        code, headers, out, err = self.get_pool_page( pool_config['listen'],
                                                      pool_config['pm.status_path'])
        code_only = int(code.split()[0])
        zbx_key = 'php-fpm.pool.status[{0}]'
        zbx_key = zbx_key.format(pool)
        data[zbx_key] = 0
        if code_only == 200:
          data[zbx_key] = 1
          pool_status = simplejson.loads(out)
          for key in PHP_POOL_STATUS_KEYS:
            zbx_key = 'php-fpm.pool.status[{0},{1}]'
            zbx_key = zbx_key.format(pool, key.replace(' ', '_'))
            data[zbx_key] = pool_status[key]
      except:
        zbx_key = 'php-fpm.pool.status[{0}]'
        zbx_key = zbx_key.format(pool)
        data[zbx_key] = 0
        pass
    return data

  def get_discovery(self):
    data = []
    pool_list = self.get_pools_config()
    for pool in pool_list:
      element = { '{#PHPFPMPOOLNAME}': pool }
      data.append(element)
    return {'php-fpm.pool.discovery': data}

  def get_pools_config(self):
    f = []
    pool_config = ConfigParser.ConfigParser()
    root_path = '/home/dev/python-zabbix/scripts/fpm/pool.d/'
    root_path = '/etc/php5/fpm/pool.d'
    poolfilelist = [
      os.path.join(root_path, f) for f in
      os.listdir(root_path)
      if os.path.isfile(os.path.join(root_path, f))
    ]
    pool_config.read(poolfilelist)
    pool_config_dict = simplejson.loads(simplejson.dumps(pool_config._sections))
    return pool_config_dict

def parse_args():
    ''' Parse the script arguments
    '''
    parser = optparse.OptionParser()

    parser.add_option("-d", "--dry", action="store_true",
                          help="Performs Supervisord calls but do not send "
                               "anything to the Zabbix server. Can be used "
                               "for both Update & Discovery mode")
    parser.add_option("-D", "--debug", action="store_true",
                      help="Enable debug mode. This will prevent bulk send "
                           "operations and force sending items one after the "
                           "other, displaying result for each one")
    parser.add_option("-v", "--verbose", action="store_true",
                      help="When used with debug option, will force value "
                           "display for each items managed. Beware that it "
                           "can be pretty too much verbose, specialy for LLD")

    mode_group = optparse.OptionGroup(parser, "Program Mode")
    mode_group.add_option("--update-items", action="store_const",
                          dest="mode", const="update_items",
                          help="Get & send items to Zabbix. This is the default "
                               "behaviour even if option is not specified")
    mode_group.add_option("--discovery", action="store_const",
                          dest="mode", const="discovery",
                          help="If specified, will perform Zabbix Low Level "
                               "Discovery on Supervisord. "
                               "Default is to get & send items")
    parser.add_option_group(mode_group)
    parser.set_defaults(mode="update_items")

    general_options = optparse.OptionGroup(parser, "Supervisord "
                                                   "configuration options")

    parser.add_option_group(general_options)

    zabbix_options = optparse.OptionGroup(parser, "Zabbix configuration")
    zabbix_options.add_option("--zabbix-server", metavar="HOST", default="localhost",
                               help="The hostname of Zabbix server or "
                                    "proxy, default is localhost.")
    zabbix_options.add_option("--zabbix-port", metavar="PORT", default=10051,
                               help="The port on which the Zabbix server or "
                                    "proxy is running, default is 10051.")
    parser.add_option_group(zabbix_options)

    (options, args) = parser.parse_args()

    return (options, args)

def main():

    (options, args) = parse_args()
    hostname = platform.node()

    try:
      phpfpm = PhpFpm()
    except:
      return 1

    zbx_container = protobix.DataContainer()
    data = {}
    if options.mode == "update_items":
        zbx_container.set_type("items")
        data[hostname] = phpfpm.get_metrics()
        data[hostname]['php-fpm.zbx_version'] = __version__

    elif options.mode == "discovery":
        zbx_container.set_type("lld")
        data[hostname] = phpfpm.get_discovery()

    zbx_container.add(data)
    zbx_container.set_host(options.zabbix_server)
    zbx_container.set_port(int(options.zabbix_port))
    zbx_container.set_debug(options.debug)
    zbx_container.set_verbosity(options.verbose)
    zbx_container.set_dryrun(options.dry)

    try:
        zbx_response = zbx_container.send(zbx_container)
    except protobix.SenderException as zbx_exception:
        if options.debug:
            print ZBX_CONN_ERR % zbx_exception.err_text
        return 2
    else:
        return 0

if __name__ == '__main__':
    ret = main()
    print ret