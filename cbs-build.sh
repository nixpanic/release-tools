#!/bin/sh
#
# Build packages in the CentOS Community Build System (CBS).
#
# This script assumes:
# - you have a working 'cbs' command, and the required certs
# - the working-dir is a git repository of git@github.com:CentOS-Storage-SIG/glusterfs.git
# - fedpkg is useable for EPEL packages (TODO: replace with SIG buildroot)

check_cbs() {
	cbs moshimoshi > /dev/null
}

# build a src.rpm and write the path to stdout
local_get_srpm() {
	local OS=${1}
	fedpkg --release=${OS} srpm 2>/dev/null | awk '/^Wrote/ {print $2}'
}

local_mockbuild() {
	local OS=${1}
	fedpkg --release=${OS} mockbuild
}

# A branch has a format like 'sig-storage7-gluster-38'
GIT_BRANCH=$(git describe --contains --all HEAD)
PREFIX='sig-storage'
OS=$(sed -e "s/^${PREFIX}//" -e "s/-.*//" <<< "${GIT_BRANCH}")
PROJECT=$(cut -d - -f 3 <<< "${GIT_BRANCH}")
VERSION=$(cut -d - -f 4 <<< "${GIT_BRANCH}")

# TODO: do some validation of the git repo, branch and parsed values

# fail on an error
set -e

# run very verbose
set -x

# check if the 'cbs' command works
check_cbs

# do a local mock build
local_mockbuild el${OS}

# create the src.rpm (well, re-create it and get the path)
SRPM=$(local_get_srpm el${OS})
test -n ${SRPM}

# do a scratch build in the CBS
BUILDTARGET_PREFIX='storage'
cbs build --scratch ${BUILDTARGET_PREFIX}${OS}-${PROJECT}-${VERSION}-el${OS} ${SRPM}

# TODO: fail in case the git repo is dirty ('git status --short'?)
GIT_REPO='git@github.com:CentOS-Storage-SIG/glusterfs.git'
GIT_REMOTE=$(git remote -v | grep -m 1 -w "${GIT_REMOTE}" | cut -f 1)
test -n ${GIT_REMOTE}
git push ${GIT_REMOTE} ${GIT_BRANCH}

# scratch build worked, build for real
cbs build ${BUILDTARGET_PREFIX}${OS}-${PROJECT}-${VERSION}-el${OS} ${SRPM}

# build finished successfully, mark the build for testing
NVR=$(basename ${SRPM} .src.rpm)
test -n ${NVR}
cbs tag-pkg ${BUILDTARGET_PREFIX}${OS}-${PROJECT}-${VERSION}-testing ${NVR}
