# Welcome to the open_plan gui repository
![open_plan_logo (10X1)](https://user-images.githubusercontent.com/70587431/144256918-974fcefd-29f5-4b2f-b68b-6468327ef50b.png)

Learn more about the open_plan project on our [website](https://open-plan-tool.org/).

## Credits
This code is based from previous open-source work done building a user interface to the [multi-vector-simulator](https://github.com/rl-institut/multi-vector-simulator) tool in the [Horizon2020](https://elandh2020.eu/) ELAND project. In open_plan project's scope a new design and more features are added, based on feedback collected in workshops held with stakeholders.

## Basic structure

This repository contains the code for the user interface. The simulations are performed by [multi-vector-simulator](https://github.com/rl-institut/multi-vector-simulator) on a dedicated server (see the [open-plan-tool/simulation-server](https://github.com/open-plan-tool/simulation-server) repository). Once a simulation is over the results are sent back to the user interface were one can analyse them.

![open-plan structure](https://github.com/open-plan-tool/gui/assets/4399407/89e1ff2a-1dd0-40e6-91a3-465c77426867)




# Getting Started

## Deploy locally using and using our open plan MVS server

Prior to be able to develop locally, you might need to install postgres, simply google `install postgres` followed by your os name (`linux/mac/windows`)

1. Create a virtual environment
2. Activate your virtual environment
3. Move to the `app` folder with `cd app`
4. Install local development dependencies with `pip install -r requirements/local.txt`
5. Create a `.env` file (inside `app`) and define the following environment variables (only replace content surrounded by `<>`).
```
EPA_SECRET_KEY=<randomly generated string>
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=<your db name>
SQL_USER=<your user name>
SQL_PASSWORD=<your password>
SQL_HOST=localhost
SQL_PORT=5432
TRUSTED_HOST=http://127.0.0.1:8000
DEBUG=(True|False)
MVS_HOST_API=<the simulation server you wish to use>
```
6. Execute the `local_setup.sh` file (`. local_setup.sh` on linux/mac `bash local_setup.sh` on windows) you might have to make it executable first. Answer yes to the question
7. Start the local server with `python manage.py runserver`
8. You can then login with `testUser` and `ASas12,.` or create your own account

## Deploy using Docker Compose
The following commands should get everything up and running, using the web based version of the MVS API.

You need to be able to run docker-compose inside your terminal. If you can't you should install [Docker desktop](https://www.docker.com/products/docker-desktop/) first.


* Clone the repository locally `git clone --single-branch --branch main https://github.com/open-plan-tool/gui.git open_plan_gui`
* Move inside the created folder (`cd open_plan_gui`)
* Edit the `.envs/epa.postgres` and `.envs/db.postgres` environment files
   * Change the value assigned to `EPA_SECRET_KEY` with a [randomly generated one](https://randomkeygen.com/)
   * Make sure to replace dummy names with you preferred names
   * The value assigned to the variables `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` in `.envs/db.postgres` should match the ones of
   the variables `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD` in `.envs/epa.postgres`, respectively

   * Define an environment variable `MVS_HOST_API` in `.envs/epa.postgres` and set the url of the simulation server
   you wish to use for your models (for example `MVS_API_HOST="<url to your favorite simulation server>"`), you can deploy your own [simulation server](https://github.com/open-plan-tool/simulation-server) locally if you need

    * Assign the domain of your website (including `http://` or `https://`) to `TRUSTED_HOST` , see https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins for more information

Next you can either provide the following commands inside a terminal (with ubuntu you might have to prepend `sudo`)
* `docker-compose --file=docker-compose-postgres.yml up -d --build` (you can replace `postgres` by `mysql` if you want to use mysql)
* `docker-compose --file=docker-compose-postgres.yml exec -u root app_pg sh initial_setup.sh` (this will also load a default testUser account with sample scenario).

Or you can run a python script with the following command
* `python deploy.py -db postgres`

Finally
* Open browser and navigate to http://localhost:8080 (or to http://localhost:8090 if you chose to use `mysql` instead of `postgres`): you should see the login page of the open_plan app
* You can then login with `testUser` and `ASas12,.` or create your own account

### Proxy settings (optional)
If you use a proxy you will need to set `USE_PROXY=True` and edit `PROXY_ADDRESS=http://proxy_address:port` with your proxy settings in `.envs/epa.postgres`.

>**_NOTE:_** If you wish to use mysql instead of postgres, simply replace `postgres` by `mysql` and `app_pg` by `app` in the above commands or filenames
<hr>

>**_NOTE:_** Grab a cup of coffee or tea for this...
<hr>

>**_NOTE:_** Grab a cup of coffee or tea for this...
<hr>

## Test Account
> You can access a preconfigured project using the following login credentials:  `testUser:ASas12,.`
<hr>

## Tear down (uninstall) docker containers
To remove the application (including relevant images, volumes etc.), one can use the following commands in terminal:

`docker-compose down --file=docker-compose-postgres.yml -v`

you can add `--rmi local` if you wish to also remove the images (this will take you a long time to rebuild the docker containers from scratch if you want to redeploy the app later then)

Or you can run a python script with the following command

`python deploy.py -db postgres --down`
