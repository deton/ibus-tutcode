# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-
#
# ibus-tutcode - The TUT-Code engine for IBus (based on ibus-skk)
#
# Copyright (c) 2007-2008 Huang Peng <shawn.p.huang@gmail.com>
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gobject
import ibus
from ibus import keysyms
from ibus import modifier
import sys, os, os.path, time
import tutcode
try:
    from gtk import clipboard_get
except ImportError:
    clipboard_get = lambda a : None

from gettext import dgettext
_  = lambda a : dgettext("ibus-tutcode", a)
N_ = lambda a : a

# Work-around for older IBus releases.
if not hasattr(ibus, 'ORIENTATION_HORIZONTAL'):
    ibus.ORIENTATION_HORIZONTAL = 0

class CandidateSelector(tutcode.CandidateSelector):
    def __init__(self, lookup_table, keys, page_size, pagination_start):
        self.__lookup_table = lookup_table
        self.__keys = keys
        super(CandidateSelector, self).__init__(page_size, pagination_start)

    def set_candidates(self, candidates):
        super(CandidateSelector, self).set_candidates(candidates)
        if len(candidates) > self.pagination_start:
            self.__lookup_table.clean()
            for candidate, annotation in candidates[self.pagination_start:]:
                self.__lookup_table.append_candidate(ibus.Text(candidate))

    def lookup_table_visible(self):
        if self.index() >= self.pagination_start:
            return True
        return False
        
    def next_candidate(self, move_over_pages=True):
        super(CandidateSelector, self).next_candidate(move_over_pages)
        if self.lookup_table_visible():
            if self.index() == self.pagination_start:
                self.__lookup_table.set_cursor_pos(0)
            elif not move_over_pages:
                self.__lookup_table.set_cursor_pos(self.index() -
                                                   self.pagination_start)
        return self.candidate()

    def previous_candidate(self, move_over_pages=True):
        super(CandidateSelector, self).previous_candidate(move_over_pages)
        if self.lookup_table_visible():
            if self.index() == self.pagination_start:
                self.__lookup_table.set_cursor_pos(0)
            elif not move_over_pages:
                self.__lookup_table.set_cursor_pos(self.index() -
                                                   self.pagination_start)
        return self.candidate()

    def candidate(self):
        candidate = super(CandidateSelector, self).candidate()
        if candidate is None:
            return None
        return candidate

    def set_index(self, index):
        super(CandidateSelector, self).set_index(index)
        if self.index() >= self.pagination_start:
            self.__lookup_table.set_cursor_pos(self.index() -
                                               self.pagination_start)

    def key_to_index(self, key):
        if key not in self.__keys:
            raise IndexError('%s is not a valid key' % key)
        pos = self.__keys.index(key)
        if self.__lookup_table.set_cursor_pos_in_current_page(pos):
            index = self.__lookup_table.get_cursor_pos()
            return self.__pagination_start + index
        else:
            raise IndexError('invalid key position %d' % pos)

    def pos_to_index(self, pos):
        if self.__lookup_table.set_cursor_pos_in_current_page(pos):
            index = self.__lookup_table.get_cursor_pos()
            return self.__pagination_start + index
        else:
            raise IndexError('invalid key position %d' % pos)

class Engine(ibus.EngineBase):
    config = None
    sysdict = None

    __select_keys = [u'q', u'w', u'e', u'r', u't', u'y', u'u', u'i', u'o', u'p',
                     u'a', u's', u'd', u'f', u'g', u'h', u'j', u'k', u'l', u';',
                     u'z', u'x', u'c', u'v', u'b', u'n', u'm', u',', u'.', u'/']
     
    __input_mode_prop_names = {
        tutcode.INPUT_MODE_HIRAGANA : u"InputMode.Hiragana",
        tutcode.INPUT_MODE_KATAKANA : u"InputMode.Katakana"
        }

    __prop_name_input_modes = dict()
    for key, val in __input_mode_prop_names.items():
        __prop_name_input_modes[val] = key

    __input_mode_labels = {
        tutcode.INPUT_MODE_HIRAGANA : u"あ",
        tutcode.INPUT_MODE_KATAKANA : u"ア"
        }

    def __init__(self, bus, object_path):
        super(Engine, self).__init__(bus, object_path)
        self.__is_invalidate = False
        labels = [ibus.Text(c + u':') for c in self.__select_keys]
        page_size = self.config.get_value('page_size')
        pagination_start = self.config.get_value('pagination_start')
        self.__lookup_table = ibus.LookupTable(page_size=page_size,
                                               round=False,
                                               labels=labels)
        if hasattr(self.__lookup_table, 'set_orientation'):
            self.__lookup_table.set_orientation(ibus.ORIENTATION_HORIZONTAL)

        self.__candidate_selector = CandidateSelector(self.__lookup_table,
                                                      self.__select_keys,
                                                      page_size,
                                                      pagination_start)
        usrdict = tutcode.UsrDict(self.config.usrdict_path)
        self.__tutcode = tutcode.Context(usrdict, self.sysdict,
                                 self.__candidate_selector)
        self.__tutcode.tutcode_rule = self.config.get_value('tutcode_rule')
        self.__initial_input_mode = self.config.get_value('initial_input_mode')
        self.__tutcode.translated_strings['dict-edit-prompt'] = \
            _(u'DictEdit').decode('UTF-8')
        self.__tutcode.custom_tutcode_rule = \
            self.config.get_value('custom_tutcode_rule')
        self.__tutcode.cancel_keys = self.config.get_value('cancel_keys')
        self.__tutcode.backspace_keys = self.config.get_value('backspace_keys')
        self.__tutcode.conv_keys = self.config.get_value('conv_keys')
        self.__tutcode.next_keys = self.config.get_value('next_keys')
        self.__tutcode.prev_keys = self.config.get_value('prev_keys')
        self.__tutcode.commit_keys = self.config.get_value('commit_keys')
        self.__tutcode.purge_keys = self.config.get_value('purge_keys')
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(self.__initial_input_mode)
        self.__prop_dict = dict()
        self.__prop_list = self.__init_props()
        self.__input_mode = tutcode.INPUT_MODE_HIRAGANA
        self.__update_input_mode()
        self.__suspended_mode = None


    def __init_props(self):
        tutcode_props = ibus.PropList()

        input_mode_prop = ibus.Property(key=u"InputMode",
                                        type=ibus.PROP_TYPE_MENU,
                                        label=u"あ",
                                        tooltip=_(u"Switch input mode"))
        self.__prop_dict[u"InputMode"] = input_mode_prop

        props = ibus.PropList()
        props.append(ibus.Property(key=u"InputMode.Hiragana",
                                   type=ibus.PROP_TYPE_RADIO,
                                   label=_(u"Hiragana")))
        props.append(ibus.Property(key=u"InputMode.Katakana",
                                   type=ibus.PROP_TYPE_RADIO,
                                   label=_(u"Katakana")))

        for prop in props:
            self.__prop_dict[prop.key] = prop

        prop_name = self.__input_mode_prop_names[self.__tutcode.input_mode]
        self.__prop_dict[prop_name].set_state(ibus.PROP_STATE_CHECKED)

        input_mode_prop.set_sub_props(props)
        tutcode_props.append(input_mode_prop)
        return tutcode_props

    def __update_input_mode(self):
        if self.__input_mode == self.__tutcode.input_mode:
            return False
        self.__input_mode = self.__tutcode.input_mode
        prop_name = self.__input_mode_prop_names[self.__input_mode]
        self.__prop_dict[prop_name].set_state(ibus.PROP_STATE_CHECKED)
        self.update_property(self.__prop_dict[prop_name])
        prop = self.__prop_dict[u"InputMode"]
        prop.label = self.__input_mode_labels[self.__input_mode]
        self.update_property(prop)
        self.__invalidate()

    def __get_clipboard(self, clipboard, text, data):
        clipboard_text = clipboard.wait_for_text()
        if clipboard_text:
            handled, output = \
                self.__tutcode.append_text(clipboard_text.decode('UTF-8'))
            self.__check_handled(handled, output)

    def process_key_event(self, keyval, keycode, state):
        # ignore key release events
        if state & modifier.RELEASE_MASK:
            return False
        # ignore alt+key events
        if state & modifier.MOD1_MASK:
            return False

        if self.__tutcode.conv_state == tutcode.CONV_STATE_SELECT:
            if keyval == keysyms.Page_Up or keyval == keysyms.KP_Page_Up:
                self.page_up()
                return True
            elif keyval == keysyms.Page_Down or keyval == keysyms.KP_Page_Down:
                self.page_down()
                return True
            elif keyval == keysyms.Up or keyval == keysyms.Left:
                self.__tutcode.previous_candidate(False)
                self.__update()
                return True
            elif keyval == keysyms.Down or keyval == keysyms.Right:
                self.__tutcode.next_candidate(False)
                self.__update()
                return True
            elif state & modifier.CONTROL_MASK == 0 and \
                    self.__candidate_selector.lookup_table_visible():
                try:
                    index = self.__candidate_selector.\
                        key_to_index(unichr(keyval).lower())
                    handled, output = self.__tutcode.select_candidate(index)
                    if handled:
                        if output:
                            self.commit_text(ibus.Text(output))
                        gobject.idle_add(self.__tutcode.usrdict.save,
                                         priority = gobject.PRIORITY_LOW)
                        self.__lookup_table.clean()
                        self.__update()
                        return True
                except IndexError:
                    pass
        elif (self.__tutcode.dict_edit_level() > 0 or \
                self.__tutcode.conv_state == tutcode.CONV_STATE_START) and \
                (state & modifier.CONTROL_MASK) and \
                unichr(keyval).lower() in (u'y', u'v'):
            if unichr(keyval).lower() == u'y':
                clipboard = clipboard_get ("PRIMARY")
            else:
                clipboard = clipboard_get ("CLIPBOARD")
            if clipboard:
                clipboard.request_text(self.__get_clipboard)
            
        if keyval == keysyms.Tab:
            keychr = u'\t'
        elif keyval == keysyms.Return:
            keychr = u'return'
        elif keyval == keysyms.Escape:
            keychr = u'escape'
        elif keyval == keysyms.BackSpace:
            keychr = u'backspace'
        else:
            keychr = unichr(keyval)
            if 0x20 > ord(keychr) or ord(keychr) > 0x7E:
                # If the pre-edit buffer is visible, always handle key events:
                # http://github.com/ueno/ibus-skk/issues/#issue/5
                return len(self.__tutcode.preedit) > 0
        if state & modifier.CONTROL_MASK:
            # Some systems return 'J' if ctrl:nocaps xkb option is
            # enabled and the user press CapsLock + 'j':
            # http://github.com/ueno/ibus-skk/issues/#issue/22
            keychr = u'ctrl+' + keychr.lower()
        return self.__tutcode_press_key(keychr)

    def __check_handled(self, handled, output):
        if output:
            self.commit_text(ibus.Text(output))
        if handled:
            gobject.idle_add(self.__tutcode.usrdict.save,
                             priority = gobject.PRIORITY_LOW)
            self.__update()
            return True
        return False
        
    def __tutcode_press_key(self, keychr):
        handled, output = self.__tutcode.press_key(keychr)
        if self.__check_handled(handled, output):
            return True
        # If the pre-edit buffer is visible, always handle key events:
        # http://github.com/ueno/ibus-skk/issues/#issue/5
        return len(self.__tutcode.preedit) > 0

    def __invalidate(self):
        if self.__is_invalidate:
            return
        self.__is_invalidate = True
        gobject.idle_add(self.__update, priority = gobject.PRIORITY_LOW)

    def page_up(self):
        if self.__lookup_table.page_up():
            self.page_up_lookup_table()
            self.__candidate_selector.previous_candidate(True)
            self.__update()
            return True
        return False

    def page_down(self):
        if self.__lookup_table.page_down():
            self.page_down_lookup_table()
            self.__candidate_selector.next_candidate(True)
            self.__update()
            return True
        return False

    def cursor_up(self):
        if self.__lookup_table.cursor_up():
            self.cursor_up_lookup_table()
            self.__candidate_selector.previous_candidate(False)
            self.__update()
            return True
        return False

    def cursor_down(self):
        if self.__lookup_table.cursor_down():
            self.cursor_down_lookup_table()
            self.__candidate_selector.next_candidate(False)
            self.__update()
            return True
        return False

    def candidate_clicked(self, index, button, state):
        try:
            index = self.__candidate_selector.pos_to_index(index)
            handled, output = self.__tutcode.select_candidate(index)
            if handled:
                if output:
                    self.commit_text(ibus.Text(output))
                gobject.idle_add(self.__tutcode.usrdict.save,
                                 priority = gobject.PRIORITY_LOW)
                self.__lookup_table.clean()
                self.__update()
        except IndexError:
            pass
        
    def __possibly_update_config(self):
        if self.__tutcode.usrdict.path != self.config.usrdict_path:
            self.__tutcode.usrdict = tutcode.UsrDict(self.config.usrdict_path)
        self.__tutcode.tutcode_rule = self.config.get_value('tutcode_rule')
        self.__initial_input_mode = self.config.get_value('initial_input_mode')

    # ABBREV_CURSOR_COLOR = (65, 105, 225)
    # INPUT_MODE_CURSOR_COLORS = {
    #     tutcode.INPUT_MODE_HIRAGANA: (139, 62, 47),
    #     tutcode.INPUT_MODE_KATAKANA: (34, 139, 34)
    #     }

    def __update(self):
        prompt, prefix, word, suffix = self.__tutcode.preedit_components()
        prefix_start = len(prompt)
        word_start = prefix_start + len(prefix)
        suffix_start = word_start + len(word)
        suffix_end = suffix_start + len(suffix)
        attrs = ibus.AttrList()
        # Display "[DictEdit]" way different from other components
        # (black/lightsalmon).
        attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0),
                                              0, prefix_start))
        attrs.append(ibus.AttributeBackground(ibus.RGB(255, 160, 122),
                                              0, prefix_start))
        if self.__tutcode.conv_state == tutcode.CONV_STATE_SELECT:
            # Use colors from tutcode-henkan-face-default (black/darkseagreen2).
            attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0),
                                                  word_start, suffix_start))
            attrs.append(ibus.AttributeBackground(ibus.RGB(180, 238, 180),
                                                  word_start, suffix_start))
            attrs.append(ibus.AttributeUnderline(ibus.ATTR_UNDERLINE_SINGLE,
                                                 suffix_start, suffix_end))
        else:
            attrs.append(ibus.AttributeUnderline(ibus.ATTR_UNDERLINE_SINGLE,
                                                 word_start, suffix_end))
        # Color cursor, currently disabled.
        #
        # if self.__tutcode.abbrev:
        #     cursor_color = self.ABBREV_CURSOR_COLOR
        # else:
        #     cursor_color = self.INPUT_MODE_CURSOR_COLORS.get(\
        #         self.__tutcode.input_mode)
        # attrs.append(ibus.AttributeBackground(ibus.RGB(*cursor_color),
        #                                       suffix_end, suffix_end + 1))
        # preedit = ''.join((prompt, prefix, word, suffix, u' '))
        #
        preedit = ''.join((prompt, prefix, word, suffix))
        self.update_preedit_text(ibus.Text(preedit, attrs),
                                 len(preedit), len(preedit) > 0)
        visible = self.__candidate_selector.lookup_table_visible()
        self.update_lookup_table(self.__lookup_table, visible)
        self.__update_input_mode()

        if self.__tutcode.conv_state is not tutcode.CONV_STATE_SELECT:
            gobject.idle_add(self.__possibly_update_config,
                             priority = gobject.PRIORITY_LOW)

        self.__is_invalidate = False

    def fill_lookup_table(self, candidates):
        self.__lookup_table.clean()
        for candidate in candidates:
            self.__lookup_table.append_candidate(ibus.Text(candidate))
        self.__lookup_table_hidden = False

    def lookup_table_visible(self):
        return not self.__lookup_table_hidden and \
            self.__lookup_table.get_number_of_candidates() > 1

    def show_lookup_table(self):
        self.__lookup_table_hidden = False
        super(Engine, self).show_lookup_table()

    def hide_lookup_table(self):
        self.__lookup_table_hidden = True
        super(Engine, self).hide_lookup_table()

    def focus_in(self):
        self.register_properties(self.__prop_list)
        # skipped at first focus_in after ibus startup
        if self.__suspended_mode is not None:
            self.__tutcode.activate_input_mode(self.__suspended_mode)
            self.__suspended_mode = None
        self.__update_input_mode()

    def focus_out(self):
        self.__suspended_mode = self.__tutcode.input_mode
        # self.__tutcode.kakutei()
        # self.commit_text(ibus.Text(u''))
        self.__lookup_table.clean()
        self.__update()
        self.reset()

    def reset(self):
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(self.__initial_input_mode)

    def property_activate(self, prop_name, state):
        # print "PropertyActivate(%s, %d)" % (prop_name, state)
        if state == ibus.PROP_STATE_CHECKED:
            input_mode = self.__prop_name_input_modes[prop_name]
            self.__tutcode.activate_input_mode(input_mode)
            self.__update_input_mode()
