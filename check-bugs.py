#!/usr/bin/python
#
# Script to verify the status of Gluster bugs filed in the Red Hat Bugzilla.
#
# The Bug Life Cycle documents the valid status of a Bug:
# - http://www.gluster.org/community/documentation/index.php/Bug_report_life_cycle
#
# Date: Sun 6 April 2014
# Author: Niels de Vos <ndevos@redhat.com>
#

from urllib2 import urlopen, URLError
from json import loads

from bugzilla import Bugzilla

import re

import os, os.path
from os import popen


GERRIT_URL  = 'https://review.gluster.org'
GERRIT_CHANGES_Q = '/changes/?q=status:%s+topic:bug-%s'
GERRIT_REVIEW_Q = '/changes/%s/revisions/current/review'

BZ_URL = 'https://bugzilla.redhat.com/xmlrpc.cgi'
#BZ_URL = 'https://partner-bugzilla.redhat.com/xmlrpc.cgi'

class GitRepo:
    def __init__(self, project, path):
        self.project = project
        self.path = path
        if not os.path.exists(path):
            fd = popen('git clone http://review.gluster.org/%s %s' % (project, path))

    def findCommit(self, after, branch, changeid):
        os.chdir(self.path)

        cmd = 'git log --format=raw --after="%s" origin/%s | grep -E -e "^commit [[:alnum:]]+$" -e "^[[:space:]]*Change-Id:" | grep -B1 "^[[:space:]]*Change-Id: %s$"' % (after, branch, changeid)
        fd = popen(cmd)
        commit = fd.readline()
        if len(commit) == 0:
            return None
        return commit.split()[1]


    def findTag(self, commit):
        os.chdir(self.path)

        # all tags with the commit are returned in a { timestamp : hash } format
        lines = popen('git tag --contains %s | xargs -n1 git log -1 --format="%%ct %%H"' % commit).readlines()

        if len(lines) == 0:
            # no tag contains this commit
            return None

        tags = dict()
        for l in lines:
            (ts, hash) = l.split()
            tags[int(ts)] = hash

        # sort on timestamps, and pick the most recent (hopefully a release)
        ts = tags.keys()
        ts.sort()
        hash = tags[ts[-1]]

        # this is expected to return only one line
        lines = popen('git describe --exact-match %s 2> /dev/null' % hash).readlines()

        if len(lines) == 0:
            # no tag contains this commit
            return None

        return lines[0].strip()


class ChangeStatus:
    def __init__(self, change):
        self.changeid = change['change_id']
        self.id = change['change_id'][:7]
        self.created = change['created']
        self.branch = change['branch']
        self.status = change['status']
        self.subject = change['subject']
        self.project = change['project']
        self.repo = None

    def isMerged(self):
        return (self.status == 'MERGED')

    def setGitRepo(self, path):
        repo = GitRepo(self.project, path)
        self.repo = repo

    def resolveCommit(self):
        if not self.isMerged():
            self.commit = None
        else:
            self.commit = self.repo.findCommit(self.created, self.branch, self.changeid)
        return (self.commit != None)

    def resolveTag(self):
        if not self.resolveCommit():
            self.tag = None
        else:
            self.tag = self.repo.findTag(self.commit)
        return (self.tag != None)

    def isForQA(self):
        ON_QA_TAGS = ['qa', 'alpha', 'beta']

        if not self.resolveTag():
            return False
        for qa_tag in ON_QA_TAGS:
            if re.search(qa_tag, self.tag):
                return True

    def isReleased(self):
        if not self.resolveTag():
            return False
        elif self.isForQA():
            return False
        else:
            return True

    def __repr__(self):
        return u'[%s] %s %s (%s)' % (self.branch, self.id, self.subject, self.status)

    def __cmp__(self, other):
        return cmp(self.changeid, other.changeid)

class BugStateException(Exception):
    pass

class BugStatus:
    def __init__(self, bug):
        self._bug = bug
        self._changes = list()

    def addChangeStatus(self, change):
        if change not in self._changes:
            self._changes.append(change)

    def getChangeStates(self):
        return self._changes

    def verifyState(self):
        state = self._bug.status

        if len(self._changes) == 0:
            # no changes posted: status -> NEW/ASSIGNED/CLOSED
            valid = (state in ('NEW', 'ASSIGNED', 'CLOSED'))
            if not valid:
                raise BugStateException('No change posted, but bug is in %s' % state)

        for change in self._changes:
            if not change.isMerged():
                # status -> POST
                valid = (state == 'POST')
                error = u'Bug should be in POST, change %s is not merged yet' % change.id
            elif change.isForQA():
                # status -> ON_QA/VERIFIED
                valid = (state in ('ON_QA', 'VERIFIED'))
                error = u'Bug should be ON_QA, use %s for verification of the fix' % change.tag
            elif change.isReleased():
                # status -> CLOSED
                valid = (state == 'CLOSED')
                error = u'Bug should be CLOSED, %s contains a fix' % change.tag
            else:
                # status -> MODIFIED
                valid = (state == 'MODIFIED')
                error = u'Change %s has been merged, but bug is not in MODIFIED' % change.id

            if not valid:
                raise BugStateException(error)

        return True

    def __repr__(self):
        s = (u'%s' % self._bug)
        for c in self._changes:
            s += u'\n  %s' % c
        return s

    def __cmp__(self, other):
        return cmp(self._bug, other._bug)



__verbose = False
def verbose(msg):
    if __verbose:
        print(msg.encode('utf-8'))

def _getGerritResponse(url):
    try:
        response = urlopen(url)
    except URLError, ue:
        print(('An error occured: %s' % ue).encode('utf-8'))
        return None

    # thrown away the first line, it contains: )]}'
    _badline = response.readline()

    reply = response.read()
    return loads(reply)


def getOpenChangesForBug(bug):
    changeUrl = GERRIT_URL + GERRIT_CHANGES_Q % ('open', bug)
    return _getGerritResponse(changeUrl)


def getMergedChangesForBug(bug):
    changeUrl = GERRIT_URL + GERRIT_CHANGES_Q % ('merged', bug)
    return _getGerritResponse(changeUrl)


def getOpenBugs(bz):
#    q = bz.build_query(product='GlusterFS', status='MODIFIED')
#    q = bz.build_query(product='GlusterFS', status=['POST', 'ON_QA'])
    q = bz.build_query(product='GlusterFS', status=['NEW', 'ASSIGNED', 'POST', 'MODIFIED', 'ON_QA', 'VERIFIED'])
    return bz.query(q)


bz = Bugzilla(url=BZ_URL)
bzs = getOpenBugs(bz)
#bzs = [bz.getbug(765051)]
#bzs = [bz.getbug(841617)]

bugs = list()

for bug in bzs:
    if 'Tracking' in bug.keywords:
        continue

    verbose(u'checking Bug %s' % bug)
    bs = BugStatus(bug)
    bugs.append(bs)

    openChanges = getOpenChangesForBug(bug.id)
    mergedChanges = getMergedChangesForBug(bug.id)

    for change in openChanges + mergedChanges:
        cs = ChangeStatus(change)
        cs.setGitRepo('/tmp/gluster.org/' + cs.project)
        bs.addChangeStatus(cs)

    try:
        bs.verifyState()
        verbose(u'Bug #%d has been verified -> OK' % bug.id)
    except BugStateException, be:
        print(u'%s' % bs).encode('utf-8')
        print(u'  ** %s **' % be).encode('utf-8')

