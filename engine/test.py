# -*- coding: utf-8 -*-

from __future__ import with_statement
import unittest
import os, os.path
import tutcode
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

        self.__tutcode = tutcode.Context(usrdict=tutcode.UsrDict(usrdict_path),
                                 sysdict=tutcode.SysDict(sysdict_path),
                                 candidate_selector=tutcode.CandidateSelector())

    def testusrdict(self):
        usrdict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    ".mazegaki-ibus-corrupted")
        with open(usrdict_path, 'w+') as fp:
            fp.write(u'あい /愛/\n'.encode('EUC-JP'))
        try:
            usrdict = tutcode.UsrDict(usrdict_path, 'UTF-8')
            self.assertNotEqual(usrdict, None)
            self.assertTrue(usrdict.read_only)
        except Exception, e:
            self.fail("can't open user dictionary: %s" % e.message)
        finally:
            os.unlink(usrdict_path)

    def testkeyconfig(self):
        self.__tutcode.cancel_keys = ('ctrl+u',)
        self.assertEqual(self.__tutcode.cancel_keys, ('ctrl+u',))

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

if __name__ == '__main__':
    unittest.main()
