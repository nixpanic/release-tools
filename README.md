## Gluster Release Tools

This repository is a collection of tools/scripts used by the GlusterFS release managers to do GlusterFS releases.

### Scripts

- `close-bugs.sh`
  This script is used to close bugs after a release. Run it as,

  ```
  ./close-bugs.sh <file-with-bugs-to-be-closed> <version-string-for-current-release> <url-to-mailing-list-announcement>
  ```

- `close-bugs-eol.sh`
  Use this script to close bugs when a version is End-Of-Life. Modify the `3.8` in the example commands:

  ```
  bugzilla query --from-url='https://bugzilla.redhat.com/buglist.cgi?f1=version&f2=bug_status&o1=regexp&o2=notequals&product=GlusterFS&v1=^3.8&v2=CLOSED' \
                 --ids > /tmp/bugs_to_close.txt

  ./close-bugs-eol.sh /tmp/bugs_to_close.txt 3.8
  ```

- `release_notes.sh`
  This script is used to generate the release notes for a release. Run it as,

  ```
  ./release_notes.sh <previous version released> <current version to be released> <path to glusterfs repository>
  ```

