#!/bin/sh
#
# Example usage:
# 1. list all bugs that are open (against 3.8):
#    https://bugzilla.redhat.com/buglist.cgi?f1=version&f2=bug_status&o1=regexp&o2=notequals&product=GlusterFS&v1=^3.8&v2=CLOSED
# 
# 2. create a file with all BZs (numbers only):
#    $ bugzilla query --from-url='https://bugzilla.redhat.com/buglist.cgi?f1=version&f2=bug_status&o1=regexp&o2=notequals&product=GlusterFS&v1=^3.8&v2=CLOSED' \
#                     --ids > /tmp/bugs_to_close.txt
# 
# 3. close the bugs:
#    $ ./close-bugs-eol.sh /tmp/bugs_to_close.txt 3.8
# 

declare BUGSLIST VERSION

if [ "x$DRY_RUN" != "x" ]; then
  DR="echo"
fi

check_for_command()
{
  env bugzilla --version >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "`bugzilla` command is missing"
    echo "Install `python-bugzilla` before running this script again"
    exit 1
  fi
}

close_bugs()
{
	COMMENT="This bug is getting closed because the ${VERSION} version is marked End-Of-Life. There will be no further updates to this version. Please open a new bug against a version that still receives bugfixes if you are still facing this issue in a more current release."

	xargs -n 8 ${DR} bugzilla modify \
		--status=CLOSED \
		--close=EOL \
		--comment="${COMMENT}" ${@}
}

check_for_command

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file-with-bugs-to-be-closed> <eol-version>"
  exit 1
fi

BUGSLIST=$1
VERSION=$2

cat $BUGSLIST | close_bugs
