#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name = 'protobix',
    version = '0.0.3',
    zip_safe = True,
    
    author = 'Jean Baptiste Favre',
    author_email = 'jean-baptiste.favre@blablacar.com',
    description = 'Implementation of Zabbix Sender protocol',
    long_description = ( 'This module implements Zabbix Sender Protocol.\n'
                         'It allows to build list of items and send items and send '
                         'them as trapper.\n'
                         'It currently supports items as well as Low Level Discovery.' ),
    license = 'GPL',
    url='http://www.blablacar.com/',
    packages=['protobix'],
   )
