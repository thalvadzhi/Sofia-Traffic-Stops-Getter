#!/usr/bin/python3

from sys import argv
import os

if 'username' in argv[1].lower():
    print(os.environ['GIT_USERNAME'])
    exit()

if 'password' in argv[1].lower():
    print(os.environ['GIT_PASSWORD'])
    exit()

exit(1)