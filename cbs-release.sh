#!/bin/sh
#
# Promote builds from testing to release in the CentOS Community Build System
# (CBS).
#
# This script assumes:
# - you have a working 'cbs' command, and the required certs
# - you pass a build/NVR on the cmdline (like 'glusterfs-3.8.9-1.el6')

check_cbs() {
	cbs moshimoshi > /dev/null
}

# print the tags of a build to stdout
cbs_get_tags() {
	local NVR=${1}

	cbs buildinfo ${NVR} | grep ^Tags | cut -d ' ' -f 2-
}

if [ -z "${1}" -o "${1}" = '-h' -o "${1}" = '--help' ]
then
	echo "Usage: ${0} <name-version-release.dist>"
	exit
fi
NVR=${1}

# fail on an error
set -e

# check if the 'cbs' command works
check_cbs

# find the build and verify the tags are not empty
TAGS=$(cbs_get_tags ${NVR})
if [ -z "${TAGS}" ]
then
	echo "Build ${NVR} could not be found."
	exit
fi

PROMOTE_BUILD=''
for TAG in ${TAGS}
do
	PREFIX=$(cut -d - -f 1 <<< "${TAG}")
	PROJECT=$(cut -d - -f 2 <<< "${TAG}")
	VERSION=$(cut -d - -f 3 <<< "${TAG}")
	STATE=$(sed 's/.*-//' <<< "${TAG}")

	case "${STATE}" in
	'testing')
		# build is in testing, it may be promoted
		PROMOTE_BUILD=1
		;;
	'release')
		# build is released already, nothing to do
		echo "Build ${NVR} has been tagged in -release already."
		exit
		;;
	*)
		# skip, we don't care about this tag
		;;
	esac
done

if [ -n "${PROMOTE_BUILD}" ]
then
	cbs tag-pkg ${PREFIX}-${PROJECT}-${VERSION}-release ${NVR}
else
	echo "Build ${NVR} is not in -testing yet, not promoting to -release."
fi
