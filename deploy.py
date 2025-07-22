import argparse
import os
import warnings

LOGS = {"gui": "app", "server": "nginx", "queues": "djangoq"}
DB = "postgres"

parser = argparse.ArgumentParser(
    prog="python deploy.py",
    description="Deploy docker container to host the open-plan GUI app",
)
parser.add_argument(
    "--down",
    dest="docker_down",
    action="store_true",
    help="Use this option if you want to take the deployed app down and clear the volumes (caution this will erase the database!)",
)
parser.add_argument(
    "--update",
    dest="docker_update",
    action="store_true",
    help="Use this option if you made modification to the GUI app files and want to update the deployed app.",
)
parser.add_argument(
    "--sudo",
    dest="sudo",
    action="store_true",
    help="Use this option if wou wish to run the deploy commands as sudo (posix OS only)",
)

parser.add_argument(
    "--logs",
    dest="logs",
    type=str,
    nargs="?",
    default=None,
    help=f"Use this option with one of ({', '.join(LOGS.keys())}) to display a log of the wished docker containers",
)

parser.add_argument(
    "-db",
    dest="database",
    nargs="?",
    type=str,
    default=None,
    help="Legacy option, only PostgreSQL databases are supported",
)


def get_docker_service_name(logs):
    answer = LOGS.get(logs, None)
    if answer is not None:
        answer = f"{answer}_pg"
    return answer


if __name__ == "__main__":

    args = parser.parse_args()
    app_name = "app_pg"
    list_cmds = []

    # legacy option
    if args.database:
        if args.database != "postgres":
            # must be PostgreSQL
            raise Exception("Only postgres DB supported")
        else:
            warnings.warn(
                "db option no longer supported, postgres is mandatory",
                DeprecationWarning,
            )

    if args.docker_down is True:
        if (
            input(
                "This will delete the data in your open-plan app database, are you sure you want to proceed? (Y/[n]) "
            )
            != "Y"
        ):
            exit()
        list_cmds.append(f"docker-compose --file=docker-compose-{DB}.yml down -v")

    if args.docker_update is True:
        if args.docker_down is False:
            list_cmds.append(f"docker-compose --file=docker-compose-{DB}.yml down")
        list_cmds.append(f"docker-compose --file=docker-compose-{DB}.yml up -d --build")
        list_cmds.append(
            f"docker-compose --file=docker-compose-{DB}.yml exec -u root {app_name} sh update_gui.sh"
        )
    else:
        if args.docker_down is False:
            log_service_name = get_docker_service_name(args.logs)
            if log_service_name is not None:
                list_cmds.append(
                    f"docker-compose --file=docker-compose-{DB}.yml logs {log_service_name}"
                )
            else:
                list_cmds.append(
                    f"docker-compose --file=docker-compose-{DB}.yml up -d --build"
                )
                list_cmds.append(
                    f"docker-compose --file=docker-compose-{DB}.yml exec -u root {app_name} sh initial_setup.sh"
                )

    for cmd in list_cmds:
        if args.sudo is True:
            cmd = f"sudo {cmd}"
        os.system(cmd)
