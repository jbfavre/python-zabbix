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

TODO
