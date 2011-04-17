#!/bin/sh
set -e
set -x

autopoint
aclocal -I m4
automake --add-missing --copy
autoconf
./configure $*
