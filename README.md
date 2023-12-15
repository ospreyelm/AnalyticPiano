# Overview

ANALYTIC PIANO (formerly HarmonyLab) is an open-source application for the study of music theory and keyboard skills that takes input from a MIDI keyboard and outputs staff notation. Various analytical vocabularies of melody and harmony are represented. As a practice aid and exercise platform that operates across aural, visual, and tactile domains, this tool accelerates the acquisition of fluency in certain fundamentals of tonal music.

# Supported Web Browsers

As of December 2023, Google Chrome, Microsoft Edge, Opera, and Chromium all include the WebMIDI support on which this app depends. There is cross-platform support for WebMIDI on desktop and laptop computers (Apple desktop OS, Windows, Linux) but iPads unfortunately lack this support.

# Heroku Deployment

This application can be deployed to any platform that supports python and django. [Heroku](https://heroku.com/) is one such platform, a cloud platform as a service provider (PaaS) that provides for easy deployments from GitHub.

Create a Heroku app. Deploy from the desired branch of this Github repository; the Python buildpack and the Heroku Postgres add-on will be supplied on the basis of `./Procfile`, `./Pipfile`, and `./runtime.txt`.

Add the following **Config Variables** on the Settings page:

```
SECRET_KEY = your-password
DJANGO_SETTINGS_MODULE = harmony.settings.heroku
ALLOWED_HOSTS = ["your-app-name.herokuapp.com"]
```

Note that automatic deployments are good for testing but these should be disabled when the site is in active use.

To manage the app via the Heroku CLI and to and create an admin account for the database, use these terminal commands:

```bash
$ heroku login # one-time setup
$ heroku apps # view app names for your login
$ heroku run python manage.py migrate --app HEROKU_APP_NAME
$ heroku run python manage.py createsuperuser --app HEROKU_APP_NAME
```

# Running Locally on Linux or WSL2

• Get [Python 3.10.13](http://python.org/downloads/) and [Pip](http://www.pip-installer.org/). Typical setup commands:
```bash
wget https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tgz
tar -xzf Python-3.10.13.tgz 
cd Python-3.10.13
./configure --enable-optimizations # ~1 minute
make -j 2 # ~5 minutes
sudo make install # ~1 minutes
# optional: run `python3.10` to check installation (should show "Python 3.10.13") then `exit()`
cd ../
sudo rm -rf ./Python-3.10.13
sudo rm -rf ./Python-3.10.13.tgz 
# optional: run `ls ./Python-3.10.13*` to check removal of installation files
```

• Clone the app from Github
```bash
mkdir AnalyticPiano && cd AnalyticPiano
git clone --single-branch --branch main https://github.com/ospreyelm/HarmonyLab.git clone-of-main
```

• Setup virtual environment, watching out for and resolving any errors with pipenv lock
```bash
sudo apt-get install python3.10-venv # may not be necessary
python3.10 -m venv apvenv
source apvenv/bin/activate
cd clone-of-main
pip install pipenv
pipenv lock
pipenv install
```

• Setup the database, having already installed postgresql
```bash
sudo service postgresql start # `service` on WSL2, otherwise `systemctl`
psql -U postgres
```
```psql
CREATE DATABASE analyticpiano;
\q
```

• Run the app locally as follows
```sh
cd AnalyticPiano/clone-of-main
source ../apvenv/bin/activate
export DJANGO_SETTINGS_MODULE="harmony.settings.local"
./manage.py makemigrations
./manage.py migrate
./manage.py createsuperuser # optional: create admin account
./manage.py runserver
```
Open `http://127.0.0.1:8000` in a browser, per terminal instructions (usually the keystroke to terminate the server is Ctrl+C). Remember to deactivate the virtual environment when you are done.
```sh
deactivate
```

# Reminders for local development

• Certain changes to the app will require makemigrations and migrate to be run (see above).
• Any changes to Pipfile must be followed up with `pipenv lock` and `pipenv install`.
• Otherwise, for general use, the following command will suffice:

```sh
cd AnalyticPiano/clone-of-main && source ../apvenv/bin/activate && export DJANGO_SETTINGS_MODULE="harmony.settings.local" && sudo service postgresql start && ./manage.py runserver
```

# Using a local copy of a production database on WSL2

For WSL2 users who wish to run a local copy of a production database and access it via pgAdmin on Windows proper, locate and edit the config files:
```bash
psql -U postgres -c 'SHOW config_file'
sudo nano /etc/postgresql/13/main/pg_hba.conf # adapt this line as appropriate
```
—then edit the line under "Database administrative login," which should be the first line of settings, to show not `peer` but `trust`—
```
local  all  postgres  trust
```
—then exit and save. Next:
```bash
sudo nano /etc/postgresql/13/main/postgresql.conf # adapt this line as appropriate
```
—then edit the listen_addresses value to `"*"` and exit and save. Finally for the command line:
```bash
sudo service postgresql restart
```

Now in pgAdmin, add a new server with the name wsl2 (for example) and the host address 127.0.0.1. The default username and password for postgres are postgres and password; enter these or the credentials you have setup via postgresql on WSL2. Create a backup from your production database and restore (in the role of postgres) this to a newly created database called analyticpiano on the wsl2 server. Make sure that the encoding of the backup matches that of the template database on WSL2 (probably SQL_ASCII); include all pre-data, data, and post-data; but omit owner, privilege, tablespace, unlogged table data, and comments.
