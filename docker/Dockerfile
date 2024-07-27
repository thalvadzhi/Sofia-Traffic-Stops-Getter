FROM balenalib/raspberry-pi:latest

ARG SSH_KEY
RUN eval "$(ssh-agent -s)" & ssh-add $SSH_KEY
ARG path_to_repo=/home/sumc
ARG path_to_crontab_file=/home/cron

RUN apt update && apt install -y git python3 python3-pip python3-distutils libgeos-dev libopenblas-dev
RUN mkdir ${path_to_repo}
RUN mkdir ${path_to_crontab_file}

RUN python3 -m pip install --upgrade pip

RUN apt install -y cron

# this line is added so it invalidates the cache of the clone everytime the code in the repo changes
ADD https://api.github.com/repos/thalvadzhi/Sofia-Traffic-Stops-Getter/git/refs/heads/master delete.json
RUN git clone git@github.com:thalvadzhi/Sofia-Traffic-Stops-Getter.git ${path_to_repo}


RUN python3 -m pip install -r $path_to_repo/requirements.txt
# RUN apt remove -y --purge python3-pip && apt autoremove -y
COPY ./crontab_config ${path_to_crontab_file}
RUN crontab ${path_to_crontab_file}/crontab_config

RUN chmod +x ${path_to_repo}/utils/ask_pass.py
#ENV GIT_ASKPASS ${path_to_repo}/utils/ask_pass.py
#ENV GIT_USERNAME raspberry-getter
#ENV GIT_PASSWORD ${RASPBERRY_GETTER_TOKEN}

COPY entry_script.sh /home/sumc
RUN chmod +x ${path_to_repo}/entry_script.sh

RUN git config --global user.name raspberry-getter
RUN git config --global user.email devthebear@gmail.com
RUN git config --global --add safe.directory ${path_to_repo}

WORKDIR ${path_to_repo}

CMD ["./entry_script.sh"]
