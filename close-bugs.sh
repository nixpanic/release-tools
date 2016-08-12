#!/bin/sh

declare BUGSLIST VERSION ANNOUNCEURL

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
	COMMENT="This bug is getting closed because a release has been made available that should address the reported issue. In case the problem is still not fixed with glusterfs-${VERSION}, please open a new bug report.

glusterfs-${VERSION} has been announced on the Gluster mailinglists [1], packages for several distributions should become available in the near future. Keep an eye on the Gluster Users mailinglist [2] and the update infrastructure for your distribution.

[1] ${ANNOUNCEURL}
[2] https://www.gluster.org/pipermail/gluster-users/"

	xargs -n 8 ${DR} bugzilla modify \
		--fixed_in=glusterfs-${VERSION} \
		--status=CLOSED \
		--close=CURRENTRELEASE \
		--comment="${COMMENT}" ${@}
}

check_for_command

if [ $# -ne 3 ]; then
  echo "Usage: $0 <file-with-bugs-to-be-closed> <version-string-for-current-release> <url-to-mailing-list-announcement>"
  exit 1
fi

BUGSLIST=$1
VERSION=$2
ANNOUNCEURL=$3

cat $BUGSLIST | close_bugs
