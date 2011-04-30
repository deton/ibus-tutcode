# vim:set noet ts=4:
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

engine_tutcode_PYTHON = \
	engine.py \
	factory.py \
	main.py \
	tutcode.py \
	tutcode_command.py \
	tutcode_rule.py \
	$(NULL)
engine_tutcodedir = $(pkgdatadir)/engine

libexec_SCRIPTS = ibus-engine-tutcode

component_DATA = tutcode.xml
componentdir = $(datadir)/ibus/component

CLEANFILES = \
	*.pyc \
	$(NULL)

EXTRA_DIST = \
	ibus-engine-tutcode.in \
	tutcode.xml.in.in \
	test.py \
	$(NULL)

tutcode.xml: tutcode.xml.in
	$(AM_V_GEN) \
	( \
		libexecdir=${libexecdir}; \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

test:
	$(ENV) \
		DBUS_DEBUG=true \
		IBUS_TUTCODE_PKGDATADIR=$(abs_top_srcdir) \
		PYTHONPATH=$(top_srcdir) \
		$(PYTHON) $(srcdir)/test.py

