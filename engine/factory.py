# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-
#
# ibus-tutcode - The TUT-Code engine for IBus
#
# Copyright (c) 2007-2008 Huang Peng <shawn.p.huang@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import ibus
import engine
import sys, os, os.path
import tutcode
import skkdict

from gettext import dgettext
_  = lambda a : dgettext("ibus-tutcode", a)
N_ = lambda a : a

sys.path.insert(0, os.path.join(os.getenv('IBUS_TUTCODE_PKGDATADIR'), 'setup'))
import config

class EngineFactory(ibus.EngineFactoryBase):
    def __init__(self, bus):
        self.__bus = bus
        super(EngineFactory, self).__init__(self.__bus)

        self.__id = 0
        bus_config = self.__bus.get_config()
        bus_config.connect("reloaded", self.__config_reloaded_cb)
        bus_config.connect("value-changed", self.__config_value_changed_cb)
        self.__config_reloaded_cb(bus_config)

    def create_engine(self, engine_name):
        if engine_name == "tutcode":
            self.__id += 1
            return engine.Engine(self.__bus, "%s/%d" % ("/org/freedesktop/IBus/TUTCode/Engine", self.__id))

        return super(EngineFactory, self).create_engine(engine_name)

    def __load_sysdict(self, _config):
        try:
            use_mmap = _config.get_value('use_mmap')
            instances = list()
            for path in _config.sysdict_paths:
                instances.append(skkdict.SysDict(path, use_mmap=use_mmap))
            return skkdict.MultiSysDict(instances)
        except:
            return skkdict.EmptyDict()

    def __config_reloaded_cb(self, bus_config):
        engine.Engine.config = config.Config(self.__bus)
        engine.Engine.sysdict = self.__load_sysdict(engine.Engine.config)

    def __config_value_changed_cb(self, bus_config, section, name, value):
        if section == 'engine/tutcode':
            engine.Engine.config.set_value(name, value)
            if name in ('sysdict_paths', 'use_mmap'):
                engine.Engine.sysdict = self.__load_sysdict(engine.Engine.config)
