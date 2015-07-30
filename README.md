## Gluster Release Tools

This repository is a collection of tools/scripts used by the GlusterFS release managers to do GlusterFS releases.

### Scripts

- `close-bugs.sh`
  This script is used to close bugs after a release. Run it as,
  ```
./close-bugs.sh <file-with-bugs-to-be-closed> <version-string-for-current-release> <url-to-mailing-list-announcement>
  ```

  We'll add a script to generate the bugs list file soon.

