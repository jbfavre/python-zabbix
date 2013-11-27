# python-zabbix

Very simple python module implementing Zabbix Sender protocol.
You can find code in `module` subdir.

## Install

With Debian:

    apt-get install python-stdeb python-setuptools

    cd module
    python setup.py --command-packages=stdeb.command bdist_deb
    apt-get install python-simplejson
    dpkg -i deb_dist/python-zabbix_0.0.1-1_all.deb

## Usage

Once module is installed, you can use it as follow

## Send items as trappers

    #!/usr/bin/env python
    import zabbix

    zbx_container = zabbix.DataContainer("lld", "localhost", 10051)
    zbx_container.set_debug(true)
    zbx_container.set_verbosity(true)

    ''' Add items one after the other '''
    hostname="myhost"
    item="my.zabbix.item"
    value=0
    zbx_container.add_item( hostname, item, value)

    ''' or use bulk insert '''
    data = {
        "myhost1": {
            "my.zabbix.item1": 0,
            "my.zabbix.item2": "item string"
        },
        "myhost2": {
            "my.zabbix.item1": 0,
            "my.zabbix.item2": "item string"
        }
    }
    zbx_container.add(data)

    ret = zbx_container.send(zbx_container)
    if not ret:
        print "Ooops. Something went wrong when sending data to Zabbix"

    print "Everything is OK"

## Send Low Level Discovery as trappers

    #!/usr/bin/env python
    import zabbix

    zbx_container = zabbix.DataContainer("lld", "localhost", 10051)
    zbx_container.set_debug(true)
    zbx_container.set_verbosity(true)

    ''' Add items one by one '''
    hostname="myhost"
    item="my.zabbix.lld_item1"
    value=[
        { 'my.zabbix.ldd_key1': 0,
          'my.zabbix.ldd_key2': 'lld string' },
        { 'my.zabbix.ldd_key3': 1,
          'my.zabbix.ldd_key4': 'another lld string' }
    ]
    zbx_container.add_item( hostname, item, value)

    ''' or bulk insert items '''
    data = {
        'myhost1': {
            'my.zabbix.lld_item1': [
                { 'my.zabbix.ldd_key1': 0,
                  'my.zabbix.ldd_key2': 'lld string' },
                { 'my.zabbix.ldd_key3': 1,
                  'my.zabbix.ldd_key4': 'another lld string' }
            ]
        'myhost2':
            'my.zabbix.lld_item2': [
                { 'my.zabbix.ldd_key10': 10,
                  'my.zabbix.ldd_key20': 'yet an lld string' },
                { 'my.zabbix.ldd_key30': 2,
                  'my.zabbix.ldd_key40': 'yet another lld string' }
            ]
    }
    zbx_container.add(data)

    ret = zbx_container.send(zbx_container)
    if not ret:
        print "Ooops. Something went wrong when sending data to Zabbix"

    print "Everything is OK"
