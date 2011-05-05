# vim:set et sts=4 sw=4:
# -*- coding: utf-8 -*-

from __future__ import with_statement
import unittest
import os, os.path
import tutcode
import skkdict
from ibus import modifier

class TestTUTCode(unittest.TestCase):
    def setUp(self):
        # Make sure to start with new empty usrdict.
        usrdict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    ".mazegaki-ibus.dic")
        try:
            os.unlink(usrdict_path)
        except:
            pass

        sysdict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "mazegaki-ibus.dic")
        s_dict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "mazegaki.dic")
        if not os.path.exists(sysdict_path):
            if not os.path.exists(s_dict_path):
                raise RuntimeError('mazegaki.dic not found')
            with open(sysdict_path, 'a') as tp:
                with open(s_dict_path, 'r') as fp:
                    tp.write(u'request /リクエスト/\n'.encode('EUC-JP'))
                    for line in fp:
                        tp.write(line)

        self.__tutcode = tutcode.Context(usrdict=skkdict.UsrDict(usrdict_path),
                                 sysdict=skkdict.SysDict(sysdict_path),
                                 candidate_selector=tutcode.CandidateSelector())

    def testusrdict(self):
        usrdict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    ".mazegaki-ibus-corrupted")
        with open(usrdict_path, 'w+') as fp:
            fp.write(u'あい /愛/\n'.encode('EUC-JP'))
        try:
            usrdict = skkdict.UsrDict(usrdict_path, 'UTF-8')
            self.assertNotEqual(usrdict, None)
            self.assertTrue(usrdict.read_only)
        except Exception, e:
            self.fail("can't open user dictionary: %s" % e.message)
        finally:
            os.unlink(usrdict_path)

    def testinputmodechange(self):
        self.__tutcode.reset()
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        # HIRAGANA to KATAKANA
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        handled, output = self.__tutcode.press_key(u'\'')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_KATAKANA)
        # KATAKANA to HIRAGANA
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_KATAKANA)
        handled, output = self.__tutcode.press_key(u'\'')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_HIRAGANA)
        # HIRAGANA to LATIN
        handled, output = self.__tutcode.press_key(u'ctrl+\\')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_LATIN)
        # LATIN to HIRAGANA
        handled, output = self.__tutcode.press_key(u'ctrl+\\')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_HIRAGANA)

    def testromkana(self):
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        # ek -> か
        self.assertEqual(self.__tutcode.press_key(u'e'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.press_key(u'k'), (True, u'か'))
        self.assertEqual(self.__tutcode.preedit, u'')
        # toggle submode to katakana
        self.assertEqual(self.__tutcode.press_key(u'\''), (True, u''))
        # ek -> カ
        self.assertEqual(self.__tutcode.press_key(u'e'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.press_key(u'k'), (True, u'カ'))
        self.assertEqual(self.__tutcode.preedit, u'')
        # "d " -> 、
        self.assertEqual(self.__tutcode.press_key(u'd'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.press_key(u' '), (True, u'、'))
        self.assertEqual(self.__tutcode.preedit, u'')

    def testmazegaki(self):
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.assertEqual(self.__tutcode.press_key(u'a'), (True, u''))
        self.assertEqual(self.__tutcode.press_key(u'l'), (True, u''))
        self.assertEqual(self.__tutcode.press_key(u'j'), (True, u''))
        self.assertEqual(self.__tutcode.press_key(u'r'), (True, u''))
        self.assertEqual(self.__tutcode.press_key(u'k'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'▽あ')
        self.assertEqual(self.__tutcode.press_key(u'r'), (True, u''))
        self.assertEqual(self.__tutcode.press_key(u'i'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'▽あい')
        self.__tutcode.press_key(u' ')
        self.assertEqual(self.__tutcode.preedit, u'▼娃')
        self.__tutcode.press_key(u' ')
        self.assertEqual(self.__tutcode.preedit, u'▼哀')
        # space for yomi. not start conversion
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'j')
        self.__tutcode.press_key(u'g')
        self.__tutcode.press_key(u'k')
        self.__tutcode.press_key(u'e')
        self.__tutcode.press_key(u' ')
        self.__tutcode.press_key(u'q')
        self.__tutcode.press_key(u'u')
        self.assertEqual(self.__tutcode.preedit, u'▽らーゆ')
        self.__tutcode.press_key(u' ')
        self.assertEqual(self.__tutcode.preedit, u'▼辣油')

    def testtcode(self):
        self.__tutcode.reset()
        self.__tutcode.tutcode_rule = tutcode.RULE_TCODE
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u',')
        handled, output = self.__tutcode.press_key(u'1')
        self.assertTrue(handled)
        self.assertEqual(output, u'借')
        self.__tutcode.tutcode_rule = tutcode.RULE_TUTCODE
        self.__tutcode.reset()

    def testtrycode(self):
        self.__tutcode.reset()
        self.__tutcode.tutcode_rule = tutcode.RULE_TRYCODE
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u' ')
        self.__tutcode.press_key(u',')
        handled, output = self.__tutcode.press_key(u'1')
        self.assertTrue(handled)
        self.assertEqual(output, u'惜')
        self.__tutcode.tutcode_rule = tutcode.RULE_TUTCODE
        self.__tutcode.reset()

    def testabbrev(self):
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'/')
        self.__tutcode.press_key(u'r')
        self.__tutcode.press_key(u'e')
        self.__tutcode.press_key(u'q')
        self.__tutcode.press_key(u'u')
        self.__tutcode.press_key(u'e')
        self.__tutcode.press_key(u's')
        self.__tutcode.press_key(u't')
        self.assertEqual(self.__tutcode.preedit, u'▽request')
        self.__tutcode.press_key(u' ')
        self.assertEqual(self.__tutcode.preedit, u'▼リクエスト')
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'o')
        handled, output = self.__tutcode.press_key(u' ')
        self.assertTrue(handled)
        self.assertEqual(output, u'・')

        self.__tutcode.reset();
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'/')
        handled, output = self.__tutcode.press_key(u']')
        self.assertTrue(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.preedit, u'▽]')

        # Ignore "" in abbrev mode (Issue#16).
        self.__tutcode.reset();
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'/')
        handled, output = self.__tutcode.press_key(u'(')
        self.assertTrue(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.preedit, u'▽(')

        self.__tutcode.reset();
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'/')
        handled, output = self.__tutcode.press_key(u'A')
        self.assertTrue(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.preedit, u'▽A')

    def testbushu(self):
        self.__tutcode.reset()
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'u')
        self.__tutcode.press_key(u'q')
        self.assertEqual(self.__tutcode.preedit, u'▲口')
        self.__tutcode.press_key(u'b')
        handled, output = self.__tutcode.press_key(u'a')
        self.assertTrue(handled)
        self.assertEqual(output, u'味')

        # one level commit
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'b')
        self.__tutcode.press_key(u',')
        self.assertEqual(self.__tutcode.preedit, u'▲言')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.assertEqual(self.__tutcode.preedit, u'▲言▲')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.assertEqual(self.__tutcode.preedit, u'▲言▲▲')
        self.__tutcode.press_key(u'h')
        self.__tutcode.press_key(u'd')
        self.assertEqual(self.__tutcode.preedit, u'▲言▲▲東')
        self.__tutcode.press_key(u'return')
        self.assertEqual(self.__tutcode.preedit, u'▲言▲東')
        handled, output = self.__tutcode.press_key(u'return')
        self.assertTrue(handled)
        self.assertEqual(output, u'諌')

        # commit empty bushu
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.assertEqual(self.__tutcode.preedit, u'▲')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.assertEqual(self.__tutcode.preedit, u'▲▲')
        self.__tutcode.press_key(u'return')
        self.assertEqual(self.__tutcode.preedit, u'▲')
        handled, output = self.__tutcode.press_key(u'return')
        self.assertTrue(handled)
        self.assertEqual(output, u'')

        # exit bushu mode by backspace first bushu mark(▲)
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'a')
        self.assertEqual(self.__tutcode.preedit, u'▲')
        self.__tutcode.press_key(u'backspace')
        self.__tutcode.press_key(u'a')
        self.__tutcode.press_key(u'l')
        self.__tutcode.press_key(u'j')
        self.assertEqual(self.__tutcode.preedit, u'▽')

    def testbushuconv(self):
        output = self.__tutcode.convert_bushu(u'▲言▲▲西一')
        self.assertEqual(output, u'▲言▲襾')
        output = self.__tutcode.convert_bushu(u'▲言▲襾早')
        self.assertEqual(output, u'譚')
        # alternative char
        output = self.__tutcode.convert_bushu(u'▲ア可')
        self.assertEqual(output, u'阿')
        # subtraction
        output = self.__tutcode.convert_bushu(u'▲頭豆')
        self.assertEqual(output, u'頁')
        # addition by parts
        output = self.__tutcode.convert_bushu(u'▲性語')
        self.assertEqual(output, u'悟')
        # subtraction by parts
        output = self.__tutcode.convert_bushu(u'▲襲製')
        self.assertEqual(output, u'龍')

if __name__ == '__main__':
    unittest.main()
