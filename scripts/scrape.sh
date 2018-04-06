#!/bin/bash
#
# Sean Leavey
# <github@attackllama.com>
#
# Reject regex illustration: https://regexr.com/3mtac


wget \
    --load-cookies=cookies.txt \
    --mirror \
    --page-requisites \
    --html-extension \
    --convert-links \
    --domains my.domain.com \
    --no-parent \
    -t 0 \
    --reject-regex='^.*\/(([\/a-z\d]+(\?Navigate|\?OpenDocument&Click))|(By|\(\$All\))).*' \
    --regex-type=pcre \
    --restrict-file-names=nocontrol \
    my.domain.com/backup/my-notes-application.nsf
