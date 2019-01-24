#!/bin/bash
#
# Sean Leavey
# <github@attackllama.com>
#
# Reject regex illustration: https://regexr.com/3mtac (old) https://regexr.com/471na (new)


wget \
    --load-cookies=cookies.txt \
    --mirror \
    --page-requisites \
    --convert-links \
    --domains lns01.aei.mpg.de \
    --no-parent \
    -t 0 \
    --reject-regex='^.*\/(([\/a-z\d]+(\?Navigate|\?OpenDocument&Click))|(Contents|By%20Diary%20Date|By%20Category|.*ResortAscending|.*\$searchForm|\(\$All\))).*' \
    --regex-type=pcre \
    --restrict-file-names=nocontrol \
    https://lns01.aei.mpg.de/backup/prototypelogbook1.nsf/By%20Author?OpenView
