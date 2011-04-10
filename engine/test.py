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

    def testinputmodechange(self):
        self.__tutcode.reset()
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_NONE)
        self.__tutcode.activate_input_mode(tutcode.INPUT_MODE_HIRAGANA)
        # catch ctrl-j in HIRAGANA
        handled, output = self.__tutcode.press_key(u'ctrl+j')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_HIRAGANA)
        # HIRAGANA to KATAKANA
        handled, output = self.__tutcode.press_key(u'\'')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_KATAKANA)
        # catch ctrl-j in KATAKANA, and be still in KATAKANA
        self.__tutcode.press_key(u'ctrl+j')
        self.assert_(handled)
        self.assertEqual(output, u'')
        self.assertEqual(self.__tutcode.conv_state, tutcode.CONV_STATE_NONE)
        self.assertEqual(self.__tutcode.preedit, u'')
        self.assertEqual(self.__tutcode.input_mode, tutcode.INPUT_MODE_KATAKANA)
        # KATAKANA to HIRAGANA
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
        self.assertEqual(self.__tutcode.preedit, u'e')
        self.assertEqual(self.__tutcode.press_key(u'k'), (True, u'か'))
        self.assertEqual(self.__tutcode.preedit, u'')
        # toggle submode to katakana
        self.assertEqual(self.__tutcode.press_key(u'\''), (True, u''))
        # ek -> カ
        self.assertEqual(self.__tutcode.press_key(u'e'), (True, u''))
        self.assertEqual(self.__tutcode.preedit, u'e')
        self.assertEqual(self.__tutcode.press_key(u'k'), (True, u'カ'))
        self.assertEqual(self.__tutcode.preedit, u'')

if __name__ == '__main__':
    unittest.main()
