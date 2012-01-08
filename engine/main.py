# vim:set et sts=4 sw=4:
#
# ibus-tutcode - The TUT-Code engine for IBus
#
# Copyright (c) 2007-2011 Peng Huang <shawn.p.huang@gmail.com>
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

import os
import sys
import getopt
import ibus
import factory
import gobject
import locale

class IMApp:
    def __init__(self, exec_by_ibus):
        self.__component = ibus.Component("org.freedesktop.IBus.TUTCode",
                                          "TUT-Code Component",
                                          "1.0.2",
                                          "GPL",
                                          "KIHARA Hideto <deton@m1.interq.or.jp>")
        self.__component.add_engine("tutcode",
                                    "tutcode",
                                    "Japanese TUT-Code",
                                    "ja",
                                    "GPL",
                                    "KIHARA Hideto <deton@m1.interq.or.jp>",
                                    "",
                                    "en")
        self.__mainloop = gobject.MainLoop()
        self.__bus = ibus.Bus()
        self.__bus.connect("disconnected", self.__bus_disconnected_cb)
        self.__factory = factory.EngineFactory(self.__bus)
        if exec_by_ibus:
            self.__bus.request_name("org.freedesktop.IBus.TUTCode", 0)
        else:
            self.__bus.register_component(self.__component)

    def run(self):
        self.__mainloop.run()

    def __bus_disconnected_cb(self, bus):
        self.__mainloop.quit()


def launch_engine(exec_by_ibus):
    IMApp(exec_by_ibus).run()

def print_help(out, v = 0):
    print >> out, "-i, --ibus             executed by ibus."
    print >> out, "-h, --help             show this message."
    print >> out, "-d, --daemonize        daemonize ibus"
    sys.exit(v)

def main():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except:
        pass

    exec_by_ibus = False
    daemonize = False
    debug = False

    shortopt = "ihdD"
    longopt = ["ibus", "help", "daemonize", "Debug"]

    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopt, longopt)
    except getopt.GetoptError, err:
        print_help(sys.stderr, 1)

    for o, a in opts:
        if o in ("-h", "--help"):
            print_help(sys.stdout)
        elif o in ("-d", "--daemonize"):
            daemonize = True
        elif o in ("-i", "--ibus"):
            exec_by_ibus = True
        elif o in ("-D", "--Debug"):
            debug = True
        else:
            print >> sys.stderr, "Unknown argument: %s" % o
            print_help(sys.stderr, 1)

    if debug: # copy from ibus-table
        if not os.access(os.path.expanduser('~/.ibus/tutcode'), os.F_OK):
            os.system('mkdir -p ~/.ibus/tutcode')
        logfile = os.path.expanduser('~/.ibus/tutcode/debug.log')
        sys.stdout = open(logfile, 'a', 0)
        sys.stderr = open(logfile, 'a', 0)
        from time import strftime
        print '--- ', strftime('%Y-%m-%d: %H:%M:%S'), ' ---'

    if daemonize:
        if os.fork():
            sys.exit()

    launch_engine(exec_by_ibus)

if __name__ == "__main__":
    main()
