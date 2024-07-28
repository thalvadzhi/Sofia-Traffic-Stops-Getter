#!/usr/bin/bash
printenv  >> /etc/environment
git remote set-url origin git@github.com:thalvadzhi/Sofia-Traffic-Stops-Getter.git

cron -f