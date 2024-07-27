#!/usr/bin/bash
printenv  >> /etc/environment
eval "$(ssh-agent -s)"

ssh-add $SSH_KEY

cron -f