#!/usr/bin/bash
printenv  >> /etc/environment
git remote set-url origin git@github.com:thalvadzhi/Sofia-Traffic-Stops-Getter.git
eval "$(ssh-agent -s)"

ssh-add $SSH_KEY

cron -f