#!bin/bash
date >> server_update.log
git checkout main
git pull
git checkout production
git merge main
git log -n 1 >> server_update.log
git push
git checkout staging
git rebase -i main
git push -f
