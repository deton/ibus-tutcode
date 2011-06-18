# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-
#
# ibus-tutcode - The TUT-Code engine for IBus
# (based on ibus-skk)
#
# Copyright (C) 2011 KIHARA Hideto <deton@m1.interq.or.jp>
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

import re
from skkdict import DictBase, append_candidates
import tutcode_command
import tutcode_bushudic

CONV_STATE_NONE, \
CONV_STATE_START, \
CONV_STATE_SELECT, \
CONV_STATE_BUSHU = range(4)

INPUT_MODE_LATIN, \
INPUT_MODE_HIRAGANA, \
INPUT_MODE_KATAKANA = range(3)

RULE_TUTCODE, \
RULE_TCODE, \
RULE_TRYCODE = range(3)

RULE_NAMES = {
    RULE_TUTCODE: 'tutcode_rule',
    RULE_TCODE: 'tcode_rule',
    RULE_TRYCODE: 'trycode_rule'
}

TRANSLATED_STRINGS = {
    u'dict-edit-prompt': u'DictEdit'
}

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

class CandidateSelector(object):
    PAGE_SIZE = 10
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
        self.input_mode = INPUT_MODE_HIRAGANA

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

        self.on_keys = ('ctrl+\\',)
        self.off_keys = ('ctrl+\\',)
        self.cancel_keys = ('ctrl+g', 'ctrl+u')
        self.backspace_keys = ('ctrl+h', 'backspace')
        self.conv_keys = (' ', 'ctrl+n')
        self.next_keys = (' ', 'ctrl+n')
        self.prev_keys = ('ctrl+p',)
        self.commit_keys = ('ctrl+m', 'return')
        self.purge_keys = ('!',)

        self.usrdict = usrdict
        self.sysdict = sysdict
        self.tutcode_rule = RULE_TUTCODE
        self.translated_strings = dict(TRANSLATED_STRINGS)
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
        rulename = RULE_NAMES[self.__tutcode_rule]
        rulemod = __import__(rulename)
        rule = dict(rulemod.TUTCODE_RULE)
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
        self.__current_state().rom_kana_state = (u'', u'',
                                                 self.__tutcode_rule_tree)

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
        self.__current_state().midasi = midasi
        usr_candidates = self.__usrdict.lookup(midasi)
        sys_candidates = self.__sysdict.lookup(midasi)
        candidates = append_candidates(usr_candidates, sys_candidates)
        self.__candidate_selector.set_candidates(candidates)
        if self.next_candidate() is None:
            self.__current_state().conv_state = CONV_STATE_START
            self.__enter_dict_edit()

    def __rom_kana_has_pending(self):
        if self.__current_state().rom_kana_state is None:
            return False
        output, pending, tree = self.__current_state().rom_kana_state
        return len(pending) > 0

    def __key_is_ctrl(self, key):
        '''key is ctrl+key and non-ASCII characters?'''
        if key.is_ctrl() or \
                str(key) in ('return', 'escape', 'backspace') or \
                (len(key.letter) == 1 and \
                     (0x20 > ord(key.letter) or ord(key.letter) > 0x7E)):
            return True
        return False

    def __toggle_kana_mode(self):
        input_mode = INPUT_MODE_HIRAGANA
        if self.__current_state().input_mode == INPUT_MODE_HIRAGANA:
            input_mode = INPUT_MODE_KATAKANA
        self.__current_state().input_mode = input_mode

    def press_key(self, keystr):
        '''Process a key press event KEYSTR.

        KEYSTR is in the format of [<modifier> "+"]* <keyval>.

        The return value is a tuple (HANDLED, OUTPUT) where HANDLED is
        True if the event was handled internally (otherwise False),
        and OUTPUT is a committable string (if any).'''
        key = Key(keystr)

        # print "input_mode", self.__current_state().input_mode, str(key)
        if self.__current_state().input_mode == INPUT_MODE_LATIN:
            if str(key) in self.on_keys:
                self.activate_input_mode(INPUT_MODE_HIRAGANA)
                return (True, u'')
            if str(key) in self.off_keys:
                return (True, u'') # not pass to application
            if self.dict_edit_level() <= 0:
                return (False, u'')

        if str(key) in self.cancel_keys:
            handled = True
            if self.dict_edit_level() > 0 and \
                    self.__current_state().conv_state == CONV_STATE_NONE:
                self.__abort_dict_edit()
            elif self.__current_state().conv_state in (CONV_STATE_NONE,
                                                       CONV_STATE_START,
                                                       CONV_STATE_BUSHU):
                # Don't handle ctrl+g here if no rom-kana conversion
                # is in progress.  This allows Firefox search shortcut
                # ctrl+g (ibus-skk Issue#35).
                if self.__current_state().conv_state == CONV_STATE_NONE and \
                        not self.__rom_kana_has_pending():
                    handled = False
                input_mode = self.__current_state().input_mode
                self.reset()
                self.activate_input_mode(input_mode)
            else:
                # Stop kana-kan conversion.
                self.__current_state().midasi = None
                self.__candidate_selector.set_candidates(list())
                self.__current_state().conv_state = CONV_STATE_START
            return (handled, u'')

        if str(key) in self.backspace_keys:
            return self.delete_char()

        if self.__current_state().conv_state == CONV_STATE_NONE:
            if self.dict_edit_level() > 0 and str(key) in self.commit_keys:
                return (True, self.__leave_dict_edit())

            if str(key) in self.off_keys:
                self.activate_input_mode(INPUT_MODE_LATIN)
                return (True, u'')
            if str(key) in self.on_keys:
                return (True, u'') # not pass to application

            # Ignore ctrl+key and non-ASCII characters.
            if self.__key_is_ctrl(key):
                return (False, u'')

            if self.__current_state().input_mode == INPUT_MODE_LATIN and \
                    self.dict_edit_level() > 0:
                self.__current_state().dict_edit_output += key.letter
                return (True, u'')

            output, pending, tree = \
                self.__convert_kana(key, self.__current_state().rom_kana_state)
            # tutcode_command?
            if not isinstance(pending, unicode):
                if pending == tutcode_command.COMMAND_MAZEGAKI:
                    self.__current_state().conv_state = CONV_STATE_START
                elif pending == tutcode_command.COMMAND_ABBREV:
                    self.__current_state().conv_state = CONV_STATE_START
                    self.__current_state().abbrev = True
                elif pending == tutcode_command.COMMAND_BUSHU:
                    self.__current_state().conv_state = CONV_STATE_BUSHU
                    output += u'▲'
                elif pending == tutcode_command.COMMAND_TOGGLE_KANA:
                    self.__toggle_kana_mode()
                self.__current_state().rom_kana_state = (output, u'', tree)
                return (True, u'')
            else:
                self.__current_state().rom_kana_state = (output, pending, tree)

            if self.__current_state().conv_state == CONV_STATE_NONE and \
                    len(output) > 0:
                self.__current_state().rom_kana_state = (u'', pending, tree)
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    return (True, u'')
                return (True, output)
            return (True, u'')

        elif self.__current_state().conv_state == CONV_STATE_START:
            if str(key) in self.commit_keys:
                output = self.kakutei()
                if self.dict_edit_level() > 0:
                    self.__current_state().dict_edit_output += output
                    return (True, u'')
                return (True, output)

            # If midasi is empty, switch back to CONV_STATE_NONE
            # instead of CONV_STATE_SELECT.
            if str(key) in self.conv_keys and \
                    len(self.__current_state().rom_kana_state[0]) == 0 and \
                    len(self.__current_state().rom_kana_state[1]) == 0:
                self.__current_state().conv_state = CONV_STATE_NONE
                return (True, u'')

            # Start mazegaki conversion.
            if str(key) in self.conv_keys and \
                    len(self.__current_state().rom_kana_state[1]) == 0:
                self.__current_state().conv_state = CONV_STATE_SELECT
                midasi = self.__current_state().rom_kana_state[0]
                self.__activate_candidate_selector(midasi)
                return (True, u'')

            if str(key) in self.off_keys:
                self.reset()
                self.activate_input_mode(INPUT_MODE_LATIN)
                return (True, u'')

            # Ignore ctrl+key and non-ASCII characters.
            if self.__key_is_ctrl(key):
                return (False, u'')

            # If in abbrev mode, just append the letter to the output.
            if self.__current_state().abbrev:
                self.__current_state().rom_kana_state = \
                    (self.__current_state().rom_kana_state[0] + key.letter,
                     u'',
                     self.__tutcode_rule_tree)
                return (True, u'')

            output, pending, tree = \
                self.__convert_kana(key, self.__current_state().rom_kana_state)
            if not isinstance(pending, unicode):
                if pending == tutcode_command.COMMAND_TOGGLE_KANA:
                    self.__toggle_kana_mode()
                # ignore mazegaki/bushu start
                pending = u''
            self.__current_state().rom_kana_state = (output, pending, tree)
            return (True, u'')

        elif self.__current_state().conv_state == CONV_STATE_SELECT:
            if str(key) in self.next_keys:
                index = self.__candidate_selector.index()
                if self.next_candidate() is None:
                    self.__candidate_selector.set_index(index)
                    self.__enter_dict_edit()
                return (True, u'')
            elif str(key) in self.prev_keys:
                if self.previous_candidate() is None:
                    self.__current_state().conv_state = CONV_STATE_START
                return (True, u'')
            elif str(key) in self.purge_keys:
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
                if str(key) in self.commit_keys:
                    return (True, output)
                return (True, output + self.press_key(str(key))[1])

        elif self.__current_state().conv_state == CONV_STATE_BUSHU:
            if str(key) in self.commit_keys:
                output = self.__current_state().rom_kana_state[0]
                i = output.rfind(u'▲')
                if i != -1:
                    output = output[:i] + output[i+1:] # commit last bushu
                    output = self.convert_bushu(output)
                if len(output) == 0 or output[0] != u'▲': # toplevel
                    input_mode = self.__current_state().input_mode
                    self.reset()
                    self.activate_input_mode(input_mode)
                    if self.dict_edit_level() > 0:
                        self.__current_state().dict_edit_output += output
                        return (True, u'')
                    return (True, output)
                else:
                    self.__current_state().rom_kana_state = (output, u'',
                            self.__tutcode_rule_tree)
                    return (True, u'')

            # Ignore mazegaki conversion keys.
            if str(key) in self.conv_keys and \
                    len(self.__current_state().rom_kana_state[1]) == 0:
                return (True, u'')

            if str(key) in self.off_keys:
                self.reset()
                self.activate_input_mode(INPUT_MODE_LATIN)
                return (True, u'')

            # Ignore ctrl+key and non-ASCII characters.
            if self.__key_is_ctrl(key):
                return (False, u'')

            output, pending, tree = \
                self.__convert_kana(key, self.__current_state().rom_kana_state)
            if not isinstance(pending, unicode):
                if pending == tutcode_command.COMMAND_TOGGLE_KANA:
                    self.__toggle_kana_mode()
                elif pending == tutcode_command.COMMAND_BUSHU:
                    output += u'▲'
                # ignore mazegaki start
                pending = u''
            elif pending == u'':
                output = self.convert_bushu(output)
                if output[0] != u'▲':
                    input_mode = self.__current_state().input_mode
                    self.reset()
                    self.activate_input_mode(input_mode)
                    if self.dict_edit_level() > 0:
                        self.__current_state().dict_edit_output += output
                        return (True, u'')
                    return (True, output)
            self.__current_state().rom_kana_state = (output, pending, tree)
            return (True, u'')

    def __delete_char_from_rom_kana_state(self, state):
        tree = self.__tutcode_rule_tree
        output, pending, _tree = state
        if pending:
            return (output, u'', tree) # clear pending like tc2
        elif output:
            return (output[:-1], u'', tree)
        return None

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
            state = self.__delete_char_from_rom_kana_state(
                self.__current_state().rom_kana_state)
            if state and not (
                    # for CONV_STATE_BUSHU, if first '▲' in output is deleted,
                    # reset conv_state
                    self.__current_state().conv_state == CONV_STATE_BUSHU and
                    state[0] == u''):
                self.__current_state().rom_kana_state = state
                return (True, u'')
        if self.__current_state().conv_state in (CONV_STATE_START,
                                                 CONV_STATE_BUSHU):
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
            state = self.__append_text_to_rom_kana_state(
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

For example, in mazegaki conversion (in dict-edit mode level 2) the
elements will be "[[DictEdit]] へきくう ", "▽", "へき", "" .'''
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
        elif self.__current_state().conv_state == CONV_STATE_BUSHU:
            return (prompt,
                    prefix, # rom_kana_state[0] contains some u'▲'
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
        elif isinstance(next_output, tuple) or isinstance(next_output, list):
            katakana, hiragana = next_output
            output += self.__convert_kana_by_input_mode(katakana, hiragana)
        else: # tutcode_command (ex. mazegaki start)
            return (output, next_output, self.__tutcode_rule_tree)
        next_state = (output, u'', self.__tutcode_rule_tree)
        return next_state

    def __convert_kana_by_input_mode(self, katakana, hiragana):
        if self.__current_state().input_mode == INPUT_MODE_HIRAGANA:
            return hiragana
        elif self.__current_state().input_mode == INPUT_MODE_KATAKANA:
            return katakana

    def convert_bushu(self, str):
        m = re.match(u'(.*)▲([^▲])([^▲])$', str)
        if m:
            kanji = self.__convert_bushu_char(m.group(2), m.group(3))
            if kanji:
                return self.convert_bushu(m.group(1) + kanji)
            else:
                return str[:-1]
        else:
            return str

    def __convert_bushu_char(self, c1, c2):
        output = self.__convert_bushu_compose(c1, c2)
        if output:
            return output

        # alternative char
        a1 = tutcode_bushudic.TUTCODE_BUSHUDIC_ALTCHAR.get(c1)
        a2 = tutcode_bushudic.TUTCODE_BUSHUDIC_ALTCHAR.get(c2)
        if a1 or a2:
            if a1:
                c1 = a1
            if a2:
                c2 = a2
            output = self.__convert_bushu_compose(c1, c2)
            if output:
                return output

        # check whether composed character is new
        def _isnewchar(nc):
            if nc is None:
                return False
            if nc != c1 and nc != c2:
                return True
            return False

        # decompose
        tc11 = tc12 = None
        rows = [(row[0], row[1]) for row in tutcode_bushudic.TUTCODE_BUSHUDIC
                if row[2] == c1]
        if rows:
            tc11, tc12 = rows[0]
        tc21 = tc22 = None
        rows = [(row[0], row[1]) for row in tutcode_bushudic.TUTCODE_BUSHUDIC
                if row[2] == c2]
        if rows:
            tc21, tc22 = rows[0]

        # subtraction
        if tc11 == c2 and _isnewchar(tc12):
            return tc12
        if tc12 == c2 and _isnewchar(tc11):
            return tc11
        if tc21 == c1 and _isnewchar(tc22):
            return tc22
        if tc22 == c1 and _isnewchar(tc21):
            return tc21

        # addition by parts
        def _compose_newchar(i1, i2):
            nc = self.__convert_bushu_compose(i1, i2)
            if _isnewchar(nc):
                return nc
            return None
        output = _compose_newchar(c1, tc22)
        if output:
            return output
        output = _compose_newchar(tc11, c2)
        if output:
            return output
        output = _compose_newchar(c1, tc21)
        if output:
            return output
        output = _compose_newchar(tc12, c2)
        if output:
            return output
        output = _compose_newchar(tc11, tc22)
        if output:
            return output
        output = _compose_newchar(tc11, tc21)
        if output:
            return output
        output = _compose_newchar(tc12, tc22)
        if output:
            return output
        output = _compose_newchar(tc12, tc21)
        if output:
            return output

        # subtraction by parts
        if tc11 and tc11 == tc21 and _isnewchar(tc12):
            return tc12
        if tc11 and tc11 == tc22 and _isnewchar(tc12):
            return tc12
        if tc12 and tc12 == tc21 and _isnewchar(tc11):
            return tc11
        if tc12 and tc12 == tc22 and _isnewchar(tc11):
            return tc11
        return None

    def __convert_bushu_compose(self, c1, c2):
        output = [row[2] for row in tutcode_bushudic.TUTCODE_BUSHUDIC
                if row[0] == c1 and row[1] == c2]
        if output:
            return output[0]
        output = [row[2] for row in tutcode_bushudic.TUTCODE_BUSHUDIC
                if row[0] == c2 and row[1] == c1]
        if output:
            return output[0]
        return None
