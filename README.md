# Welcome to the open_plan gui repository
![open_plan_logo (10X1)](https://user-images.githubusercontent.com/70587431/144256918-974fcefd-29f5-4b2f-b68b-6468327ef50b.png)

Learn more about the open_plan project on our [website](https://open-plan-tool.org/).

## Credits
This code is based from previous open-source work done building a user interface to the [multi-vector-simulator](https://github.com/rl-institut/multi-vector-simulator) tool in the [Horizon2020](https://elandh2020.eu/) ELAND project. In open_plan project's scope a new design and more features are added, based on feedback collected in workshops held with stakeholders.

## Basic structure

This repository contains the code for the user interface. The simulations are performed by [multi-vector-simulator](https://github.com/rl-institut/multi-vector-simulator) on a dedicated server (see the [open-plan-tool/simulation-server](https://github.com/open-plan-tool/simulation-server) repository). Once a simulation is over the results are sent back to the user interface were one can analyse them.


# Getting Started

## Deploy locally using and using our open plan MVS server

Prior to be able to develop locally, you might need to install postgres, simply google `install postgres` followed by your os name (`linux/mac/windows`)

1. Create a virtual environment
2. Activate your virtual environment
3. Install the dependencies with `pip install -r app/requirements/postgres.txt`
4. Install extra local development dependencies with `pip install -r app/dev_requirements.txt`
5. Move to the `app` folder with `cd app`
6. Create environment variables (only replace content surrounded by `<>`)
```
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=<your db name>
SQL_USER=<your user name>
SQL_PASSWORD=<your password>
SQL_PORT=5432
DATABASE=postgres
```
8. Execute the `local_setup.sh` file (`. local_setup.sh` on linux/mac `bash local_setup.sh` on windows) you might have to make it executable first. Answer yes to the question
9. Start the local server with `python manage.py runserver`
10. You can then login with `testUser` and `ASas12,.` or create your own account

## Deploy using Docker Compose - use of MVS web API
The following commands should get everything up and running, utilzing the web based version of the MVS API.
1. `git clone --single-branch --branch main https://github.com/open-plan-tool/gui.git`
2. cd inside the created folder
4. `docker-compose --file=docker-compose-postgres.yml up -d --build` (you can replace `postgres` by `mysql` if you want to use mysql)
5. `docker-compose exec app_pg sh setup.sh` (this will also load a default testUser account with sample scenario).
6. Open browser and navigate to http://localhost:80.

>**_NOTE:_** If you use a proxy you will need to introduce modifications to app/epa.env to fit your needs.
<hr>

>**_NOTE:_** Grab a cup of coffee or tea for this...
<hr>

## Test Account
> You can access a preconfigured project using the following login credentials:  `testUser:ASas12,.`
<hr>

## Tear down
> To remove the application (including relevant images, volumes etc.), one can use the following commands in cmd:
- `docker-compose down --file=docker-compose-postgres.yml --volumes --rmi local`, or
- `docker-compose -f docker-compose_with_mvs.yml down --volumes --rmi local` if docker-compose_with_mvs.yml configuration was utilized.
<hr>

## Installation Notes
1. Docker engine should be started to run the application
2. An error might occur on `setup.sh` execution. This is because of the underlying OS and the way it handles EOL. Try to execute the commands in the file sequentially instead.
