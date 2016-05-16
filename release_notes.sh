#!/bin/bash
#
# Generate release notes in Markdown format so that they can easily be included
# in the <glusterfs-repo>/docs/release-notes/ directory.
#
# This script expects the following parameters:
#
# 1: base version (git commit, tag, ..)
# 2: target version these release notes are for (the git commit, tag ..)
# 3: path to the git repository
#
# While this script runs, the output is printed to stdout. Afterwards the
# results can also be found in /tmp/release_notes.
#

function generate_release_notes ()
{
    local orig_version=$1
    local latest_version=$2
    local repo=$3

    cd ${repo}

    # step 1: gather all BUG numbers from the commit messages
    #         use format=email so that BUG: is at the start of the line
    # step 2: split the BUG: lines at the : position, only return the 2nd part
    # step 3: filter non-numeric lines, and strip off any spaces with awk
    # step 4: sort numeric, and only get occurences once (-u for unique)
    # step 5: use xargs to pass some of the bugs to the bugzilla command
    # step 6: show progress on the current terminal, and write to a file
    git log --format=email $1..$2 | grep -w -i ^BUG \
        | cut -d: -f2 \
        | awk '/^[[:space:]]*[0-9]+[[:space:]]*$/{print $1}' \
        | sort -n -u \
        | xargs -r -n1 bugzilla query --outputformat='- [#%{id}](https://bugzilla.redhat.com/%{id}): %{summary}' -b \
        | tee /tmp/release_notes
}

function main ()
{
    generate_release_notes $1 $2 $3;
}

main "$@"
