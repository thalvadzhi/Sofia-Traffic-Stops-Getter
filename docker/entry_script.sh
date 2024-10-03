#!/usr/bin/bash
printenv  >> /etc/environment
mkdir -p /root/.ssh
#cp /run/secrets/ssh_key_stops_getter /root/.ssh/id_rsa
echo $SSH_KEY > /root/.ssh/id_rsa
chmod 400 /root/.ssh/id_rsa


git remote set-url origin git@github.com:thalvadzhi/Sofia-Traffic-Stops-Getter.git

git pull origin master

python3 get_everything.py