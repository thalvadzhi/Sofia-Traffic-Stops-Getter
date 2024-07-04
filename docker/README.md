## Building the docker image
1. Make `Sofia-Traffic-Stops-Getter/docker` your current directory.
2. Run `sudo docker build  --build-arg RASPBERRY_GETTER_TOKEN={RASPBERRY-TOKEN} -f .Dockerfile .`

where `{RASPBERRY TOKEN}` is the token for the Sofia-Traffic-Stops-Getter repo.

## Running the container

Execute the following command:

`sudo docker run -v /etc/localtime:/etc/localtime --restart unless-stopped -dt --name stops_getter thalvadzhiev/sumc_stops_
getter`

 * `--restart unless-stopped` will make sure that the container will be automatically restarted if it gets killed for any reason including if the device restarts. The only way to keep the container stopped is to stop it manually.
 * `-v /etc/localtime:/etc/localtime` will make sure the timezone of the container is synchronized with the timezone of the host

## Running with docker-compose (recommended)
Navigate to `/docker` folder and run:
```commandline
docker-compose up --detach
```