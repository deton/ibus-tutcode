# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-

from __future__ import with_statement
import ibus
import os, os.path, sys
import dbus
import json

sys.path.insert(0, os.path.join(os.getenv('IBUS_TUTCODE_PKGDATADIR'), 'engine'))
import tutcode

class Config:
    __sysdict_path_candidates = ('/usr/share/tc/mazegaki.dic',
                                 '/usr/local/share/tc/mazegaki.dic')
    __usrdict_path_unexpanded = '~/.mazegaki-ibus.dic'
    __config_path_unexpanded = '~/.config/ibus-tutcode.json'
    __defaults = {
        'use_mmap': True,
        'page_size': tutcode.CandidateSelector.PAGE_SIZE,
        'pagination_start': tutcode.CandidateSelector.PAGINATION_START,
        'tutcode_rule': tutcode.RULE_TUTCODE,
        'initial_input_mode': tutcode.INPUT_MODE_HIRAGANA,
        'use_with_vi': False
        }
    # sysdict_paths needs special treatment since IBusConfig does not
    # allow empty arrays (ibus-skk Issue#31).
    __keys = __defaults.keys() + ['sysdict_paths']

    # Options which can only be specified in ~/.config/ibus-tutcode.json.
    # This is a workaround for that currently IBus does not allows
    # several complex types (e.g. dictionary) to be stored in its
    # config mechanism.
    __file_defaults = {
        'custom_tutcode_rule': dict(),
        'on_keys': ('ctrl+\\',),
        'off_keys': ('ctrl+\\',),
        'cancel_keys': ('ctrl+g', 'ctrl+u'),
        'backspace_keys': ('ctrl+h', 'backspace'),
        'conv_keys': (' ','ctrl+n'),
        'next_keys': (' ', 'ctrl+n'),
        'prev_keys': ('ctrl+p',),
        'commit_keys': ('ctrl+m', 'return'),
        'purge_keys': ('!',),
        'vi_escape_keys': ('escape', 'ctrl+[')
        }

    __modified = dict()

    def __init__(self, bus=ibus.Bus()):
        self.__bus = bus
        self.__config = self.__bus.get_config()
        config_path = os.path.expanduser(self.__config_path_unexpanded)
        try:
            with open(config_path, 'r') as f:
                self.__config_from_file = json.load(f)
        except:
            print "Can't read config file:", self.__config_path_unexpanded, sys.exc_info()[:1]
            self.__config_from_file = dict()
        self.fetch_all()

    def fetch_all(self):
        for name in self.__keys():
            # print 'get_value engine/tutcode/%s' % name
            value = self.__config.get_value('engine/tutcode', name, None)
            if value is not None:
                self.__modified[name] = value

    def commit_all(self):
        for name in self.__keys():
            value = self.__modified.get(name)
            if value is not None:
                # print 'set_value engine/tutcode/%s' % name
                self.__config.set_value('engine/tutcode', name, value)
        
    def __sysdict_path(self):
        path = self.get_value('sysdict')
        if path is not None:
            return path
        for path in self.__sysdict_path_candidates:
            if os.path.exists(path):
                return path
        return None

    def __sysdict_paths(self):
        paths = self.get_value('sysdict_paths')
        if paths is not None:
            return paths
        path = self.__sysdict_path()
        if path:
            return [path]
        else:
            return dbus.Array(signature='s')
    sysdict_paths = property(lambda self: self.__sysdict_paths())

    def __usrdict_path(self):
        path = self.get_value('usrdict')
        if path is not None:
            return path
        return os.path.expanduser(self.__usrdict_path_unexpanded)
    usrdict_path = property(lambda self: self.__usrdict_path())

    def get_value(self, name):
        value = self.__modified.get(name)
        if value is not None:
            return value
        value = self.__config_from_file.get(name)
        if value is not None:
            return value
        value = self.__defaults.get(name)
        if value is not None:
            return value
        value = self.__file_defaults.get(name)
        if value is not None:
            return value
        return None

    def set_value(self, name, value):
        if value is not None:
            self.__modified[name] = value
        else:
            del self.__modified[name]
