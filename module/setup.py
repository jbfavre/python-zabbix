#!/usr/bin/env python

from distutils.core import setup

setup(
    name = 'protobix',
    packages = ['protobix'],
    version = '0.0.6',

    description = 'Implementation of Zabbix Sender protocol',
    long_description = ( 'This module implements Zabbix Sender Protocol.\n'
                         'It allows to build list of items and send items and send '
                         'them as trapper.\n'
                         'It currently supports items as well as Low Level Discovery.' ),    
    author = 'Jean Baptiste Favre',
    author_email = 'jean-baptiste.favre@blablacar.com',
    license = 'GPL',
    url='http://github.com/jbfavre/python-protobix/',
    download_url = 'http://github.com/jbfavre/python-protobix/tarball/0.0.5',
    keywords = ['monitoring','zabbix','trappers'],
    classifiers = [],
   )
