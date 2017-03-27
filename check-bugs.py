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

import os, os.path, subprocess
from time import time

GERRIT_URL  = 'http://review.gluster.org'
GERRIT_CHANGES_Q = '/changes/?q=status:%s+branch:%s+message:"BUG:%s"'
GERRIT_REVIEW_Q = '/changes/%s/revisions/current/review'

BZ_URL = 'https://bugzilla.redhat.com/xmlrpc.cgi'
#BZ_URL = 'https://partner-bugzilla.redhat.com/xmlrpc.cgi'

# these components do not use the Gluster Gerrit instance
BZ_COMPONENT_BLACKLIST = ( 'HDFS', 'gluster-hadoop', 'gluster-hadoop-install',
			   'project-infrastructure', 'puppet-gluster',
                           'website' )

# working directory for the cloned git repositories
REPO_DIR = os.getcwd()

# global helper functions
def isForQA(tag):
    ON_QA_TAGS = ['qa', 'alpha', 'beta', 'rc']
    for qa_tag in ON_QA_TAGS:
        if re.search(qa_tag, tag):
            return True

def isDevelTag(tag):
    DEVEL_TAGS = ['dev']
    for devel_tag in DEVEL_TAGS:
        if re.search(devel_tag, tag):
            return True

class GitRepo:
    def __init__(self, project, path):
        self.project = project
        self.path = path
        if not os.path.exists(path):
            # this raises subprocess.CalledProcessError if the repo does not exist
            cmd = 'git clone --quiet %s/%s %s' % (GERRIT_URL, project, path)
            subprocess.check_call(cmd, shell=True)
        else:
            st = os.stat(self.path)
            ts = time()
            # check if the repo is older than 12hr
            if st.st_mtime < (ts + (12 * 60 * 60)):
                os.chdir(self.path)
                subprocess.call('git fetch --all --quiet', shell=True)

    def findCommit(self, after, branch, changeid):
        os.chdir(self.path)

        cmd = 'git log --format=raw --after="%s" origin/%s | grep -E -e "^commit [[:alnum:]]+$" -e "^[[:space:]]*Change-Id:" | grep -B1 "^[[:space:]]*Change-Id: %s$"' % (after, branch, changeid)
        commit = subprocess.check_output(cmd, shell=True)
        if len(commit) == 0:
            return None
        return commit.split()[1]


    def findTag(self, commit):
        os.chdir(self.path)

        # all tags with the commit are returned
        cmd = 'git tag --contains %s' % commit
        lines = subprocess.check_output(cmd, shell=True)

        if len(lines.strip()) == 0:
            # no tag contains this commit
            return None

        # put all tags in a list
        tags = lines.split('\n')

        testing = dict()
        releases = dict()

        for tag in tags:
            # get the commit time of the tag in { timestamp : hash } format
            cmd = 'git log -1 --format="%%ct %%H" %s' % tag
            line = subprocess.check_output(cmd, shell=True)

            if len(line.strip()) == 0:
                # BUG: no tag contains this commit, that is impossible?!
                continue

            (ts, hash) = line.split()
            if isForQA(tag):
                testing[int(ts)] = hash
            elif not isDevelTag(tag):
                releases[int(ts)] = hash

        # sort on timestamps, and pick the oldest release
        if releases:
            ts = releases.keys()
            ts.sort()
            hash = releases[ts[0]]
        elif testing:
            # fallback to a tag for testing
            ts = testing.keys()
            ts.sort()
            hash = testing[ts[0]]
        else:
            # weird, only devel tags, same as no tag at all
            return None

        # this is expected to return only one line
        cmd = 'git describe --exact-match %s 2> /dev/null' % hash
        lines = subprocess.check_output(cmd, shell=True)
        return lines.strip()


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

    def isAbandoned(self):
        return (self.status == 'ABANDONED')

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
        if not self.resolveTag():
            return False
        return isForQA(self.tag)

    def isDevel(self):
        if not self.resolveTag():
            return False
        return isDevelTag(self.tag)

    def isReleased(self):
        if not self.resolveTag():
            return False
        elif self.isForQA():
            return False
        elif self.isDevel():
            return False
        else:
            return True

    def getExpectedBugStatus(self):
        bugStatus = 'POST'

        if self.isForQA():
            bugStatus = 'ON_QA'
        elif self.isReleased():
            bugStatus = 'CLOSED'
        elif self.isMerged():
            bugStatus = 'MODIFIED'

        return bugStatus

    def __repr__(self):
        return u'[%s] %s %s (%s)' % (self.branch, self.id, self.subject, self.status)

    def __cmp__(self, other):
        return cmp(self.changeid, other.changeid)

class BugStateException(Exception):
    pass


class BugStatus:
    def __init__(self, bug):
        self._order = ('NEW', 'ASSIGNED', 'POST', 'MODIFIED', 'ON_QA', 'CLOSED')
        """ _order does not have 'VERIFIED', use 'ON_QA' instead """
        self._bug = bug
        self._changes = list()

    def addChangeStatus(self, change):
        if change not in self._changes:
            self._changes.append(change)

    def getChangeStates(self):
        return self._changes

    def getStatusOrder(self, status):
        # ON_QA and VERIFIED are the same for developers
        if status == 'VERIFIED':
            status = 'ON_QA'

        for (i, s) in enumerate(self._order):
            if status == s:
                return i

        raise BugStateException('bug status %s unknown' % status)

    def verifyState(self):
        state = self._bug.status
        bugOrder = self.getStatusOrder(state)

        if len(self._changes) == 0:
            # no changes posted: status -> NEW/ASSIGNED/CLOSED
            valid = (state in ('NEW', 'ASSIGNED', 'CLOSED'))
            if not valid:
                raise BugStateException('%s: No change posted, but bug %d is in %s' % (self._bug.assigned_to, self._bug.id, state))

        # check if all changes for this bug have been abandoned
        validChanges = [c for c in self._changes if not c.isAbandoned()]
        if state not in ('NEW', 'ASSIGNED', 'CLOSED') and len(validChanges) == 0:
            raise BugStateException('%s: Bug %d is in %s, but all changes have been abandoned' % (self._bug.assigned_to, self._bug.id, state))

        # lowest order is what the bug should have as status
        order = -1
        incorrectState = None

        for change in validChanges:
            changeStatus = change.getExpectedBugStatus()
            changeOrder = self.getStatusOrder(changeStatus)

            # the order of these if-statements should be the reverse of self._order
            if change.isReleased() and state != 'CLOSED':
                # status -> CLOSED
                error = u'Bug %d should be CLOSED, %s contains a fix' % (self._bug.id, change.tag)
            elif change.isForQA() and state not in ('ON_QA', 'VERIFIED'):
                # status -> ON_QA/VERIFIED
                error = u'Bug %d should be ON_QA, use %s for verification of the fix' % (self._bug.id, change.tag)
            elif change.isMerged() and state != 'MODIFIED':
                # status -> MODIFIED
                error = u'Bug %d should be MODIFIED, change %s has been merged' % (self._bug.id, change.id)
            else:
                # status -> POST
                error = u'Bug %d should be in POST, change %s under review' % (self._bug.id, change.id)

            # set the order to the 1st change
            if order == -1:
                order = changeOrder

            if bugOrder != order and changeOrder <= order:
                incorrectState = BugStateException('%s: %s' % (self._bug.assigned_to, error))

            if changeOrder < order:
                order = changeOrder

        if incorrectState:
            raise incorrectState

        return True

    def __repr__(self):
        s = u'%d (%s) %s: %s' % (self._bug.id, self._bug.version, self._bug.status, self._bug.summary)
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


def getOpenChangesForBug(branch, bug):
    changeUrl = GERRIT_URL + GERRIT_CHANGES_Q % ('open', branch, bug)
    return _getGerritResponse(changeUrl)


def getClosedChangesForBug(branch, bug):
    changeUrl = GERRIT_URL + GERRIT_CHANGES_Q % ('closed', branch, bug)
    return _getGerritResponse(changeUrl)


def getOpenBugs(bz):
#    q = bz.build_query(product='GlusterFS', status='MODIFIED')
#    q = bz.build_query(product='GlusterFS', status=['POST', 'ON_QA'])
    q = bz.build_query(product='GlusterFS', status=['NEW', 'ASSIGNED', 'POST', 'MODIFIED', 'ON_QA', 'VERIFIED'])
    return bz.query(q)


def getByTracker(bz, tracker):
    q = bz.build_query(status=['NEW', 'ASSIGNED', 'POST', 'MODIFIED', 'ON_QA', 'VERIFIED'], blocked=tracker)
    bzs = bz.query(q)

    if not bzs:
        return list()

    # only keep the GlusterFS product BZs
    bzs = [b for b in bzs if b.product == 'GlusterFS']

    if not bzs:
        return list()

    # a tracker can be blocked by other trackers
    addBugs = list()
    addBugs.extend(bzs)
    for b in bzs:
        addBugs.extend(getByTracker(bz, '%d' % b.id))

    return addBugs


bz = Bugzilla(url=BZ_URL)
bzs = getOpenBugs(bz)
#bzs = [bz.getbug(765051)]
#bzs = [bz.getbug(841617)]
#bzs = [bz.getbug(1153964)]
#bzs = getByTracker(bz, 'glusterfs-3.7.0')

bugs = list()

for bug in bzs:
    if 'Tracking' in bug.keywords:
        continue
    elif bug.component in BZ_COMPONENT_BLACKLIST:
        continue

    verbose(u'checking Bug %s' % bug)
    bs = BugStatus(bug)
    bugs.append(bs)

    # by default, match any branch
    branch = '^.*'
    if bug.version == 'mainline':
        branch = 'master'
    elif re.match('(\d\.?)+', bug.version):
        # bug.version can have 2+ digits (i.e. 3.7.14), the branch has only 2
        branch = 'release-%s' % ('.'.join(bug.version.split('.')[:2]))

    openChanges = getOpenChangesForBug(branch, bug.id)
    closedChanges = getClosedChangesForBug(branch, bug.id)

    allChanges = list()
    if openChanges:
        allChanges += openChanges
    if closedChanges:
        allChanges += closedChanges

    for change in allChanges:
        cs = ChangeStatus(change)
        cs.setGitRepo(os.path.join(REPO_DIR, cs.project))
        bs.addChangeStatus(cs)

    try:
        bs.verifyState()
        verbose(u'Bug #%d has been verified -> OK' % bug.id)
    except BugStateException, be:
        print(u'%s' % bs).encode('utf-8')
        print(u'  ** %s **\n' % be).encode('utf-8')

