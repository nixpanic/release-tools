## Gluster Release Tools

This repository is a collection of tools/scripts used by the GlusterFS release managers to do GlusterFS releases.

### Scripts

- `close-bugs.sh`
  This script is used to close bugs after a release. Run it as,
  ```
./close-bugs.sh <file-with-bugs-to-be-closed> <version-string-for-current-release> <url-to-mailing-list-announcement>
  ```

- `release_notes.sh`
  This script is used to generate the release notes for a release. Run it as,
  ```
./release_notes.sh <previous version released> <current version to be released> <path to glusterfs repository>
  ```

