## Building the docker image
1. Make `Sofia-Traffic-Stops-Getter/docker` your current directory.
2. Run `sudo docker build  --build-arg RASPBERRY_GETTER_TOKEN={RASPBERRY-TOKEN} -f .Dockerfile .`

where `{RASPBERRY TOKEN}` is the token for the Sofia-Traffic-Stops-Getter repo.
