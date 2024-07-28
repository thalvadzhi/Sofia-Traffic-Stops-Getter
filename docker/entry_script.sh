#!/usr/bin/bash
printenv  >> /etc/environment
cp /run/secrets/ssh_key_stops_getter /root/.ssh/id_rsa

git remote set-url origin git@github.com:thalvadzhi/Sofia-Traffic-Stops-Getter.git

cron -f