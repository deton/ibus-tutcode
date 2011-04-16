# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-
#
# ibus-tutcode - The TUT-Code engine for IBus
#
# Copyright (C) 2009-2010 Daiki Ueno <ueno@unixuser.org>
#   changed: 2010-04-13 tagomoris <tagomoris@intellilink.co.jp>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
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
import itertools
import os.path
import socket
import re
import unicodedata
from tutcode_rule import TUTCODE_RULE
import struct
import mmap

CONV_STATE_NONE, \
CONV_STATE_START, \
CONV_STATE_SELECT = range(3)

INPUT_MODE_NONE, \
INPUT_MODE_HIRAGANA, \
INPUT_MODE_KATAKANA, \
INPUT_MODE_LATIN = range(4)

INPUT_MODE_TRANSITION_RULE = {
    u'\'': {
        INPUT_MODE_HIRAGANA: INPUT_MODE_KATAKANA,
        INPUT_MODE_KATAKANA: INPUT_MODE_HIRAGANA
        },
    u'ctrl+j': {
        INPUT_MODE_LATIN: INPUT_MODE_HIRAGANA,
        INPUT_MODE_HIRAGANA: INPUT_MODE_LATIN,
        INPUT_MODE_KATAKANA: INPUT_MODE_LATIN
        },
    }

ROM_KANA_TUTCODE = 0

ROM_KANA_RULES = (TUTCODE_RULE,)

TRANSLATED_STRINGS = {
    u'dict-edit-prompt': u'DictEdit'
}

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
        self.__close()
        fp = self.__get_fp()
        while True:
            pos = fp.tell()
            line = fp.readline()
            if not line:
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
                line = midasi + u' /' + \
                    self.join_candidates(self.__dict[midasi]) + '/\n'
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

def compile_tutcode_rule(rule):
    def _compile_tutcode_rule(tree, input_state, arg):
        if len(input_state) == 0:
            return
        hd, tl = input_state[0], input_state[1:]
        if hd in tree:
            if not isinstance(tree[hd], dict):
                return
        else:
            if not tl:
                tree[hd] = arg
                return
            tree[hd] = dict()
        _compile_tutcode_rule(tree[hd], tl, arg)
    tree = dict()
    for input_state in rule:
        _compile_tutcode_rule(tree, input_state, rule[input_state])
    return tree

def hiragana_to_katakana(kana):
    diff = ord(u'ア') - ord(u'あ')
    def to_katakana(letter):
        if ord(u'ぁ') <= ord(letter) and ord(letter) <= ord(u'ん'):
            return unichr(ord(letter) + diff)
        return letter
    return u''.join(map(to_katakana, kana)).replace(u'ウ゛', u'ヴ')

def katakana_to_hiragana(kana):
    diff = ord(u'ア') - ord(u'あ')
    def to_hiragana(letter):
        if ord(u'ァ') <= ord(letter) and ord(letter) <= ord(u'ン'):
            return unichr(ord(letter) - diff)
        return letter
    return u''.join(map(to_hiragana, kana.replace(u'ヴ', u'ウ゛')))

class CandidateSelector(object):
    PAGE_SIZE = 7
    PAGINATION_START = 4

    def __init__(self, page_size=PAGE_SIZE, pagination_start=PAGINATION_START):
        self.__page_size = page_size
        self.__pagination_start = pagination_start
        self.set_candidates(list())

    page_size = property(lambda self: self.__page_size)
    pagination_start = property(lambda self: self.__pagination_start)

    def set_candidates(self, candidates):
        '''Set the list of candidates.'''
        self.__candidates = candidates
        self.__index = -1

    def next_candidate(self, move_over_pages=True):
        '''Move the cursor forward.  If MOVE_OVER_PAGES is True, skip
        to the next page instead of the next candidate.'''
        if move_over_pages and self.__index >= self.__pagination_start:
            index = self.__index + self.__page_size
            # Place the cursor at the beginning of the page.
            index -= (index - self.__pagination_start) % self.__page_size
        else:
            index = self.__index + 1
        self.set_index(index)
        return self.candidate()

    def previous_candidate(self, move_over_pages=True):
        '''Move the cursor forward.  If MOVE_OVER_PAGES is
        True, skip to the previous page instead of the previous candidate.'''
        if move_over_pages and self.__index >= self.__pagination_start:
            index = self.__index - self.__page_size
            # Place the cursor at the beginning of the page.
            index -= (index - self.__pagination_start) % self.__page_size
        else:
            index = self.__index - 1
        self.set_index(index)
        return self.candidate()

    def candidate(self):
        '''Return the current candidate.'''
        if self.__index < 0:
            return None
        return self.__candidates[self.__index] + (True,)

    def index(self):
        '''Return the current candidate index.'''
        return self.__index

    def candidates(self):
        '''Return the list of candidates.'''
        return self.__candidates[:]

    def set_index(self, index):
        '''Set the current candidate index.'''
        if 0 <= index and index < len(self.__candidates):
            self.__index = index
        else:
            self.__index = -1

class State(object):
    def __init__(self):
        self.reset()
        self.dict_edit_output = u''

    def reset(self):
        self.conv_state = CONV_STATE_NONE
        self.input_mode = INPUT_MODE_NONE

        # Current midasi in conversion.
        self.midasi = None

        # Whether or not we are in the abbrev mode.
        self.abbrev = False

        # rom-kana state is either None or a tuple
        #
        # (OUTPUT, PENDING, TREE)
        #
        # where OUTPUT is a kana string, PENDING is a string in
        # rom-kana conversion, and TREE is a subtree of
        # tutcode_rule_tree.
        #
        # See tutcode.Context#__convert_rom_kana() for the state
        # transition algorithm.
        self.rom_kana_state = None

        self.candidates = list()
        self.candidate_index = -1

class Key(object):
    __letters = {
#        'return': '\r',
        u'escape': u'\e',
        u'backspace': u'\h',
        u'tab': u'\t'
        }

    def __init__(self, keystr):
        self.__keystr = keystr
        self.__modifiers = re.findall('([^+]+)\+', keystr)
        keystr = re.sub('(?:[^+]+\+)+', '', keystr)
        self.__keyval = keystr

        if Key.__letters.has_key(keystr.lower()):
            self.__letter = Key.__letters[keystr.lower()]
        else:
            self.__letter = keystr

    def __str__(self):
        return self.__keystr

    letter = property(lambda self: self.__letter)
    keyval = property(lambda self: self.__keyval)

    def is_ctrl(self):
        return 'ctrl' in self.__modifiers

class Context(object):
    def __init__(self, usrdict, sysdict, candidate_selector):
        '''Create an TUT-Code context.

        USRDICT is a user dictionary and SYSDICT is a system dictionary.'''
        self.__usrdict = None
        self.__sysdict = None
        self.__tutcode_rule = None
        self.__custom_tutcode_rule = dict()
        self.__candidate_selector = candidate_selector
        self.__state_stack = list()
        self.__state_stack.append(State())

        self.usrdict = usrdict
        self.sysdict = sysdict
        self.tutcode_rule = ROM_KANA_TUTCODE
        self.direct_input_on_latin = False
        self.translated_strings = dict(TRANSLATED_STRINGS)
        self.debug = False
        self.reset()

    def __check_dict(self, _dict):
        if not isinstance(_dict, DictBase):
            raise TypeError('bad dict')

    def set_usrdict(self, usrdict):
        '''Set the user dictionary.'''
        self.__check_dict(usrdict)
        self.__usrdict = usrdict

    def set_sysdict(self, sysdict):
        '''Set the system dictionary.'''
        self.__check_dict(sysdict)
        self.__sysdict = sysdict

    usrdict = property(lambda self: self.__usrdict, set_usrdict)
    sysdict = property(lambda self: self.__sysdict, set_sysdict)

    def __update_tutcode_rule_tree(self):
        rule = dict(ROM_KANA_RULES[self.__tutcode_rule])
        rule.update(self.custom_tutcode_rule)
        self.__tutcode_rule_tree = compile_tutcode_rule(rule)
        
    def set_tutcode_rule(self, tutcode_rule):
        if self.__tutcode_rule != tutcode_rule:
            self.__tutcode_rule = tutcode_rule
            self.__update_tutcode_rule_tree()

    tutcode_rule = property(lambda self: self.__tutcode_rule,
                             set_tutcode_rule)

    def set_custom_tutcode_rule(self, custom_tutcode_rule):
        if self.__custom_tutcode_rule != custom_tutcode_rule:
            self.__custom_tutcode_rule = custom_tutcode_rule
            self.__update_tutcode_rule_tree()
            
    custom_tutcode_rule = property(lambda self: self.__custom_tutcode_rule,
                                    set_custom_tutcode_rule)

    def __current_state(self):
        return self.__state_stack[-1]

    def __previous_state(self):
        return self.__state_stack[-2]

    conv_state = property(lambda self: self.__current_state().conv_state)
    input_mode = property(lambda self: self.__current_state().input_mode)
    abbrev = property(lambda self: self.__current_state().abbrev)

    def reset(self):
        '''Reset the current state of rom-kana/kana-kan conversion.'''
        self.__current_state().reset()
        self.__candidate_selector.set_candidates(self.__current_state().\
                                                     candidates)

    def __enter_dict_edit(self):
        self.__current_state().candidates = \
            self.__candidate_selector.candidates()
        self.__current_state().candidate_index = \
            self.__candidate_selector.index()

        midasi = self.__current_state().midasi
        input_mode = self.__current_state().input_mode
        self.__state_stack.append(State())
        self.reset()
        self.__current_state().midasi = midasi
        self.activate_input_mode(input_mode)

    def __abort_dict_edit(self):
        assert(self.dict_edit_level() > 0)
        self.__state_stack.pop()
        # Restore candidates.
        self.__candidate_selector.set_candidates(self.__current_state().\
                                                     candidates)
        self.__candidate_selector.set_index(self.__current_state().\
                                                candidate_index)

    def __leave_dict_edit(self):
        dict_edit_output = self.__current_state().dict_edit_output
        self.__abort_dict_edit()
        if len(dict_edit_output) == 0:
            return None
        self.__current_state().candidates.insert(0, (dict_edit_output, None))
        self.__candidate_selector.set_index(0)
        output = self.kakutei()
        if self.dict_edit_level() > 0:
            self.__current_state().dict_edit_output += output
            return None
        return output

    def activate_input_mode(self, input_mode):
        '''Switch the current input mode to INPUT_MODE.'''
        self.__current_state().input_mode = input_mode
        if self.__current_state().input_mode in (INPUT_MODE_HIRAGANA,
                                                 INPUT_MODE_KATAKANA):
            self.__current_state().rom_kana_state = (u'', u'',
                                                     self.__tutcode_rule_tree)
        else:
            self.__current_state().rom_kana_state = None

    def kakutei(self):
        '''Fix the current candidate as a commitable string.'''
        if self.__current_state().midasi:
            candidate = self.__candidate_selector.candidate()
            if candidate:
                output = candidate[0]
                if candidate[2]:
                    self.__usrdict.select_candidate(self.__current_state().midasi,
                                                    candidate[:2])
            else:
                output = self.__current_state().rom_kana_state[0]
        else:
            output = self.__current_state().rom_kana_state[0]
        input_mode = self.__current_state().input_mode
        self.reset()
        self.activate_input_mode(input_mode)
        return output

    def __activate_candidate_selector(self, midasi):
        midasi, num_list = replace_num_with_hash(midasi)
        self.__current_state().midasi = midasi
        usr_candidates = self.__usrdict.lookup(midasi)
        sys_candidates = self.__sysdict.lookup(midasi)
        candidates = append_candidates(usr_candidates, sys_candidates)
        candidates = [(substitute_num(candidate[0], num_list),
                       candidate[1])
                      for candidate in candidates]
        self.__candidate_selector.set_candidates(candidates)
        if self.next_candidate() is None:
            self.__current_state().conv_state = CONV_STATE_START
            self.__enter_dict_edit()

    def __rom_kana_key_is_acceptable(self, key):
        if self.__current_state().rom_kana_state is None:
            return False
        output, pending, tree = self.__current_state().rom_kana_state
        return len(pending) > 0 and \
            key.letter in self.__current_state().rom_kana_state[2]

    def __get_next_input_mode(self, key):
        input_mode = INPUT_MODE_TRANSITION_RULE.get(str(key), dict()).\
            get(self.__current_state().input_mode)
        return input_mode

    def press_key(self, keystr):
        '''Process a key press event KEYSTR.

        KEYSTR is in the format of [<modifier> "+"]* <keyval>.

        The return value is a tuple (HANDLED, OUTPUT) where HANDLED is
        True if the event was handled internally (otherwise False),
        and OUTPUT is a committable string (if any).'''
        key = Key(keystr)
        if str(key) == 'ctrl+g':
            if self.dict_edit_level() > 0 and \
                    self.__current_state().conv_state == CONV_STATE_NONE:
                self.__abort_dict_edit()
            elif self.__current_state().conv_state in (CONV_STATE_NONE,
                                                       CONV_STATE_START):
                input_mode = self.__current_state().input_mode
                self.reset()
                self.activate_input_mode(input_mode)
            else:
                # Stop kana-kan conversion.
                self.__current_state().midasi = None
                self.__candidate_selector.set_candidates(list())
                self.__current_state().conv_state = CONV_STATE_START
            return (True, u'')

        if str(key) in ('ctrl+h', 'backspace'):
            return self.delete_char()

        if self.__current_state().conv_state == CONV_STATE_NONE:
            # If KEY will be consumed in the next rom-kana conversion,
            # skip input mode transition.
            if not self.__rom_kana_key_is_acceptable(key):
                input_mode = self.__get_next_input_mode(key)
                if input_mode is not None:
                    if self.__current_state().rom_kana_state:
                        output = self.__current_state().rom_kana_state[0]
                    else:
                        output = u''
                    self.reset()
                    self.activate_input_mode(input_mode)
                    return (True, output)

            if self.dict_edit_level() > 0 and str(key) in ('ctrl+j', 'ctrl+m', 'return'):
                return (True, self.__leave_dict_edit())

            # XXX: ctrl+j should be treated as handled? (a8ffece4 and caf9f944)
            if str(key) == 'ctrl+j':
                return (True, u'')
                
            # Ignore ctrl+key and non-ASCII characters.
            if key.is_ctrl() or \
                    str(key) in ('return', 'escape', 'backspace') or \
                    (len(key.letter) == 1 and \
                         (0x20 > ord(key.letter) or ord(key.letter) > 0x7E)):
                return (False, u'')

            if self.__current_state().input_mode == INPUT_MODE_LATIN:
                output = key.letter
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    return (True, u'')
                if self.direct_input_on_latin:
                    return (False, u'')
                else:
                    return (True, output)

            # Start rom-kan mode with abbrev enabled (/).
            if not self.__rom_kana_key_is_acceptable(key) and \
                    key.letter == '/':
                self.__current_state().conv_state = CONV_STATE_START
                self.__current_state().abbrev = True
                return (True, u'')

            self.__current_state().rom_kana_state = \
                self.__convert_kana(key, self.__current_state().rom_kana_state)
            output = self.__current_state().rom_kana_state[0]
            if self.__current_state().conv_state == CONV_STATE_NONE and \
                    len(output) > 0:
                self.__current_state().rom_kana_state = \
                    (u'',
                     self.__current_state().rom_kana_state[1],
                     self.__current_state().rom_kana_state[2])
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    return (True, u'')
                return (True, output)
            return (True, u'')

        elif self.__current_state().conv_state == CONV_STATE_START:
            # If KEY will be consumed in the next rom-kana conversion,
            # skip input mode transition.
            if not self.__rom_kana_key_is_acceptable(key) and \
                    not self.__current_state().abbrev:
                input_mode = self.__get_next_input_mode(key)
                if self.__current_state().input_mode == INPUT_MODE_HIRAGANA and \
                        input_mode == INPUT_MODE_KATAKANA:
                    kana = hiragana_to_katakana(\
                        self.__current_state().rom_kana_state[0])
                    self.kakutei()
                    if self.dict_edit_level() > 0:
                        self.__current_state().dict_edit_output += kana
                        return (True, u'')
                    return (True, kana)
                elif self.__current_state().input_mode == INPUT_MODE_KATAKANA and \
                        input_mode == INPUT_MODE_HIRAGANA:
                    kana = katakana_to_hiragana(\
                        self.__current_state().rom_kana_state[0])
                    self.kakutei()
                    if self.dict_edit_level() > 0:
                        self.__current_state().dict_edit_output += kana
                        return (True, u'')
                    return (True, kana)
                elif input_mode is not None:
                    output = self.kakutei()
                    if self.dict_edit_level() > 0:
                        self.__current_state().dict_edit_output += output
                        output = u''
                        self.activate_input_mode(input_mode)
                        return (True, output)

            if str(key) in ('ctrl+j', 'ctrl+m', 'return'):
                output = self.kakutei()
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    return (True, u'')
                if str(key) in ('ctrl+m', 'return'):
                    output += u'\n'
                return (True, output)

            # If midasi is empty, switch back to CONV_STATE_NONE
            # instead of CONV_STATE_SELECT.
            if key.letter == u' ' and \
                    len(self.__current_state().rom_kana_state[0]) == 0:
                self.__current_state().conv_state = CONV_STATE_NONE
                return (True, u'')

            # Start okuri-nasi conversion.
            if key.letter == u' ':
                self.__current_state().conv_state = CONV_STATE_SELECT
                midasi = self.__current_state().rom_kana_state[0]
                self.__activate_candidate_selector(midasi)
                return (True, u'')

            # If in abbrev mode, just append the letter to the output.
            if self.__current_state().abbrev:
                self.__current_state().rom_kana_state = \
                    (self.__current_state().rom_kana_state[0] + key.letter,
                     u'',
                     self.__tutcode_rule_tree)
                return (True, u'')

            # Ignore ctrl+key and non-ASCII characters.
            if key.is_ctrl() or \
                    str(key) in ('return', 'escape', 'backspace') or \
                    (len(key.letter) == 1 and \
                         (0x20 > ord(key.letter) or ord(key.letter) > 0x7E)):
                return (False, u'')

            self.__current_state().rom_kana_state = \
                self.__convert_kana(key, self.__current_state().rom_kana_state)
            return (True, u'')

        elif self.__current_state().conv_state == CONV_STATE_SELECT:
            if key.letter.isspace():
                index = self.__candidate_selector.index()
                if self.next_candidate() is None:
                    self.__candidate_selector.set_index(index)
                    self.__enter_dict_edit()
                return (True, u'')
            elif key.letter == 'x':
                if self.previous_candidate() is None:
                    self.__current_state().conv_state = CONV_STATE_START
                return (True, u'')
            elif key.letter == 'X':
                self.__usrdict.purge_candidate(self.__current_state().midasi,
                                               self.__candidate_selector.candidate()[0])
                input_mode = self.__current_state().input_mode
                self.reset()
                self.activate_input_mode(input_mode)
                self.__current_state().conv_state = CONV_STATE_NONE
                return (True, u'')
            else:
                output = self.kakutei()
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    output = u''
                if str(key) in ('ctrl+j', 'ctrl+m', 'return'):
                    if str(key) in ('ctrl+m', 'return'):
                        output += u'\n'
                    return (True, output)
                return (True, output + self.press_key(str(key))[1])

    def __delete_char_from_rom_kana_state(self, state):
        tree = self.__tutcode_rule_tree
        output, pending, _tree = state
        if pending:
            pending = pending[:-1]
            for letter in pending:
                tree = tree[letter]
            return (output, pending, tree)
        elif output:
            return (output[:-1], u'', tree)

    def delete_char(self):
        '''Delete a character at the end of the buffer.'''
        if self.__current_state().conv_state == CONV_STATE_SELECT:
            self.__current_state().conv_state = CONV_STATE_NONE
            output = self.kakutei()
            if self.dict_edit_level() > 0:
                self.__current_state().dict_edit_output += output[:-1]
                return (True, u'')
            return (True, output[:-1])
        if self.__current_state().rom_kana_state:
            state = self.__delete_char_from_rom_kana_state(\
                self.__current_state().rom_kana_state)
            if state:
                self.__current_state().rom_kana_state = state
                return (True, u'')
        if self.__current_state().conv_state == CONV_STATE_START:
            input_mode = self.__current_state().input_mode
            self.reset()
            self.activate_input_mode(input_mode)
            return (True, u'')
        if self.dict_edit_level() > 0 and \
                len(self.__current_state().dict_edit_output) > 0:
            self.__current_state().dict_edit_output = \
                self.__current_state().dict_edit_output[:-1]
            return (True, u'')
        return (False, u'')

    def __append_text_to_rom_kana_state(self, state, text):
        output, pending, tree = state
        # Don't append text if rom-kana conversion is in progress.
        if pending:
            return None
        return (output + text, pending, tree)

    def append_text(self, text):
        '''Append text at the end of the buffer.'''
        if self.__current_state().conv_state == CONV_STATE_SELECT:
            return (False, u'')
        if self.__current_state().rom_kana_state:
            state = self.__append_text_to_rom_kana_state(\
                self.__current_state().rom_kana_state, text)
            if state:
                self.__current_state().rom_kana_state = state
                return (True, u'')
            return (False, u'')
        if self.dict_edit_level() > 0:
            self.__current_state().dict_edit_output += text
            return (True, u'')
        return (False, u'')

    def next_candidate(self, move_over_pages=True):
        '''Select the next candidate.'''
        return self.__candidate_selector.next_candidate(move_over_pages)

    def previous_candidate(self, move_over_pages=True):
        '''Select the previous candidate.'''
        return self.__candidate_selector.previous_candidate(move_over_pages)

    def select_candidate(self, index):
        '''Select candidate at INDEX.'''
        self.__candidate_selector.set_index(index)
        if self.__candidate_selector.index() < 0:
            return (False, u'')
        output = self.kakutei()
        if self.dict_edit_level() > 0:
            self.__current_state().dict_edit_output += output
            return (True, u'')
        return (True, output)

    def dict_edit_level(self):
        '''Return the recursion level of dict-edit mode.'''
        return len(self.__state_stack) - 1

    def __dict_edit_prompt(self):
        midasi = self.__previous_state().rom_kana_state[0]
        return u'%s%s%s %s ' % (u'[' * self.dict_edit_level(),
                                self.translated_strings['dict-edit-prompt'],
                                u']' * self.dict_edit_level(),
                                midasi)

    def preedit_components(self):
        '''Return a tuple representing the current preedit text.  The
format of the tuple is (PROMPT, PREFIX, WORD, SUFFIX).

For example, in okuri-ari conversion (in dict-edit mode level 2) the
elements will be "[[DictEdit]] かんが*え ", "▽", "かんが", "*え" .'''
        if self.dict_edit_level() > 0:
            prompt = self.__dict_edit_prompt()
            prefix = self.__current_state().dict_edit_output
        else:
            prompt = u''
            prefix = u''
        if self.__current_state().conv_state == CONV_STATE_NONE:
            if self.__current_state().rom_kana_state:
                return (prompt,
                        prefix,
                        # Don't show intermediate keys in preedit like tc2.
                        # self.__current_state().rom_kana_state[1],
                        u'',
                        u'')
            else:
                return (prompt, prefix, u'', u'')
        elif self.__current_state().conv_state == CONV_STATE_START:
            return (prompt,
                    prefix + u'▽',
                    self.__current_state().rom_kana_state[0],
                    u'')
        else:
            if self.__current_state().midasi:
                candidate = self.__candidate_selector.candidate()
                if candidate:
                    return (prompt,
                            prefix + u'▼',
                            candidate[0],
                            u'')
            return (prompt,
                    prefix + u'▼',
                    self.__current_state().rom_kana_state[0],
                    u'')
        return (prompt, prefix, u'', u'')

    preedit = property(lambda self: u''.join(self.preedit_components()))

    def __convert_kana(self, key, state):
        return self.__convert_rom_kana(key.letter, state)
            
    def __convert_rom_kana(self, letter, state):
        output, pending, tree = state
        if letter not in tree:
            if letter not in self.__tutcode_rule_tree:
                return (output + letter, u'', self.__tutcode_rule_tree)
            return self.__convert_rom_kana(letter,
                                           (output, u'',
                                            self.__tutcode_rule_tree))
        if isinstance(tree[letter], dict):
            return (output, pending + letter, tree[letter])
        next_output = tree[letter]
        if isinstance(next_output, unicode):
            output += next_output
        else:
            katakana, hiragana = next_output
            output += self.__convert_kana_by_input_mode(katakana, hiragana)
        next_state = (output, u'', self.__tutcode_rule_tree)
        return next_state

    def __convert_kana_by_input_mode(self, katakana, hiragana):
        if self.__current_state().input_mode == INPUT_MODE_HIRAGANA:
            return hiragana
        elif self.__current_state().input_mode == INPUT_MODE_KATAKANA:
            return katakana
