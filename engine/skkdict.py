# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-
#
# ibus-tutcode - The TUT-Code engine for IBus (based on ibus-skk)
#
# Copyright (C) 2009-2010 Daiki Ueno <ueno@unixuser.org>
# Copyright (C) 2011 KIHARA Hideto <deton@m1.interq.or.jp>
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

from __future__ import with_statement
import os.path
import re
import mmap

class DictBase(object):
    ENCODING = 'EUC-JIS-2004'

    def split_candidates(self, line):
        '''Parse a single candidate line into a list of candidates.'''
        def seperate_annotation(candidate):
            index = candidate.find(u';')
            if index >= 0:
                return (candidate[0:index], candidate[index + 1:])
            else:
                return (candidate, None)
        return map(seperate_annotation, line.strip()[1:-1].split(u'/'))

    def join_candidates(self, candidates):
        '''Make a single candidate line from a list of candidates.'''
        def append_annotation(candidate_annotation):
            candidate, annotation = candidate_annotation
            if annotation is not None:
                return candidate + u';' + annotation
            else:
                return candidate
        return u'/'.join(map(append_annotation, candidates))

    def reload(self):
        '''Reload the dictionary.'''
        raise NotImplemented

    def lookup(self, midasi):
        '''Lookup MIDASI in the dictionary.'''
        raise NotImplemented
        
class EmptyDict(DictBase):
    def reload(self):
        pass

    def lookup(self, midasi):
        return list()
        
class SysDict(DictBase):
    def __init__(self, path, encoding=DictBase.ENCODING, use_mmap=True):
        self.__path = path
        self.__mtime = 0
        self.__encoding = encoding
        self.__mmap = None
        self.__file = None
        self.__use_mmap = use_mmap
        self.reload()

    path = property(lambda self: self.__path)

    def __get_fp(self):
        if not self.__file:
            self.__file = open(self.__path, 'r')
        if self.__use_mmap and not self.__mmap:
            try:
                self.__mmap = mmap.mmap(self.__file.fileno(), 0,
                                        prot=mmap.PROT_READ)
                self.__file.close()
                self.__file = None
            except IOError:
                pass
        return (self.__mmap or self.__file)

    def __close(self):
        if self.__file:
            self.__file.close()
            self.__file = None
        if self.__mmap:
            self.__mmap.close()
            self.__mmap = None
        
    def __del__(self):
        self.__close()

    def reload(self):
        try:
            mtime = os.path.getmtime(self.__path)
            if mtime > self.__mtime:
                self.__okuri_ari = list()
                self.__okuri_nasi = list()
                self.__load()
                self.__mtime = mtime
        except IOError, OSError:
            pass

    def __load(self):
        offsets = self.__okuri_nasi
        self.__close()
        fp = self.__get_fp()
        while True:
            pos = fp.tell()
            line = fp.readline()
            if not line: # no ';; okuri-ari entries.'
                fp.seek(0)
                break
            if line.startswith(';; okuri-ari entries.'):
                offsets = self.__okuri_ari
                pos = fp.tell()
                break
        while True:
            pos = fp.tell()
            line = fp.readline()
            if not line:
                break
            # A comment line seperating okuri-ari/okuri-nasi entries.
            if line.startswith(';; okuri-nasi entries.'):
                offsets = self.__okuri_nasi
            else:
                offsets.append(pos)
        self.__okuri_ari.reverse()

    def __search_pos(self, offsets, _cmp):
        fp = self.__get_fp()
        fp.seek(0)
        begin, end = 0, len(offsets) - 1
        pos = begin + (end - begin) / 2
        while begin <= end:
            fp.seek(offsets[pos])
            line = fp.readline()
            r = _cmp(line)
            if r == 0:
                return (pos, line)
            elif r < 0:
                end = pos - 1
            else:
                begin = pos + 1
            pos = begin + (end - begin) / 2
        return None
        
    def __lookup(self, midasi, offsets):
        midasi = midasi.encode(self.__encoding)
        def _lookup_cmp(line):
            _midasi, candidates = line.split(' ', 1)
            return cmp(midasi, _midasi)
        r = self.__search_pos(offsets, _lookup_cmp)
        if not r:
            return list()
        pos, line = r
        _midasi, candidates = line.split(' ', 1)
        candidates = candidates.decode(self.__encoding)
        return self.split_candidates(candidates)

    def lookup(self, midasi):
        offsets = self.__okuri_nasi
        if len(offsets) == 0:
            self.reload()
        try:
            return self.__lookup(midasi, offsets)
        except IOError:
            return list()

def append_candidates(x, y):
    return x + [cy for cy in y if cy[0] not in [cx[0] for cx in x]]

class MultiSysDict(DictBase):
    def __init__(self, instances):
        self.__instances = instances

    def reload(self):
        for sysdict in self.__instances:
            sysdict.reload()
            
    def lookup(self, midasi):
        return reduce(append_candidates,
                      [sysdict.lookup(midasi)
                       for sysdict in self.__instances])

class UsrDict(DictBase):
    PATH = '~/.mazegaki-ibus.dic'
    HISTSIZE = 128

    __encoding_to_coding_system = {
        'UTF-8': 'utf-8',
        'EUC-JP': 'euc-jp',
        'Shift_JIS': 'shift_jis',
        'ISO-2022-JP': 'iso-2022-jp'
        }

    __coding_system_to_encoding = dict()
    for encoding, coding_system in __encoding_to_coding_system.items():
        __coding_system_to_encoding[coding_system] = encoding

    def __init__(self, path=PATH, encoding=DictBase.ENCODING):
        self.__path = os.path.expanduser(path)
        self.__encoding = encoding
        self.reload()

    path = property(lambda self: self.__path)

    __coding_cookie_pattern = \
        re.compile('\A\s*;+\s*-\*-\s*coding:\s*(\S+?)\s*-\*-')
    def reload(self):
        self.__dict = dict()
        try:
            with open(self.__path, 'a+') as fp:
                line = fp.readline()
                if line:
                    match = re.match(self.__coding_cookie_pattern, line)
                    if match:
                        encoding = self.__coding_system_to_encoding.\
                            get(match.group(1))
                        if encoding:
                            self.__encoding = encoding
                fp.seek(0)
                for line in fp:
                    if line.startswith(';'):
                        continue
                    line = line.decode(self.__encoding)
                    midasi, candidates = line.split(' ', 1)
                    self.__dict[midasi] = self.split_candidates(candidates)
            self.__read_only = False
        except Exception:
            # print "Exception on reading usrdict", self.__path #, sys.exc_info()[:1]
            self.__read_only = True
        self.__dict_changed = False
        self.__selection_history = list()

    read_only = property(lambda self: self.__read_only)

    def lookup(self, midasi):
        return self.__dict.get(midasi, list())

    def save(self):
        '''Save the changes to the user dictionary.'''
        if not self.__dict_changed or self.__read_only:
            return
        with open(self.__path, 'w+') as fp:
            coding_system = self.__encoding_to_coding_system.\
                get(self.__encoding)
            if coding_system:
                fp.write(';;; -*- coding: %s -*-\n' % coding_system)
            for midasi in sorted(self.__dict):
                candidates = self.join_candidates(self.__dict[midasi])
                if len(candidates) > 0:
                    line = midasi + u' /' + candidates + '/\n'
                    fp.write(line.encode(self.__encoding))

    def select_candidate(self, midasi, candidate):
        '''Mark CANDIDATE was selected as the conversion result of MIDASI.'''
        del(self.__selection_history[self.HISTSIZE:])
        _midasi = None
        for index, _midasi in enumerate(self.__selection_history):
            if _midasi == midasi:
                if index > 0:
                    first = self.__selection_history[0]
                    self.__selection_history[0] =\
                        self.__selection_history[index]
                    self.__selection_history[index] = first
                break
        if _midasi is not midasi:
            self.__selection_history.insert(0, midasi)

        if midasi not in self.__dict:
            self.__dict[midasi] = list()
        elements = self.__dict[midasi]
        for index, (_candidate, _annotation) in enumerate(elements):
            if _candidate == candidate[0]:
                if index > 0:
                    first = elements[0]
                    elements[0] = elements[index]
                    elements[index] = first
                    self.__dict_changed = True
                return
        elements.insert(0, candidate)
        self.__dict_changed = True

    def purge_candidate(self, midasi, candidate):
        '''Remove CANDIDATE from the list of candidates for MIDASI.'''
        candidates = self.__dict[midasi]
        for _candidate in candidates:
            if _candidate[0] == candidate:
                candidates.remove(_candidate)
                self.__dict_changed = True
