# Overview

ANALYTIC PIANO (formerly HarmonyLab) is an open-source application for the study of music theory and keyboard skills that takes input from a MIDI keyboard and outputs staff notation. Various analytical vocabularies of melody and harmony are represented. As a practice aid and exercise platform that operates across aural, visual, and tactile domains, this tool accelerates the acquisition of fluency in certain fundamentals of tonal music.

# Supported Web Browsers

As of June 2022, Google Chrome, Microsoft Edge, Opera, and Chromium all include the WebMIDI support on which this app depends. There is cross-platform support for WebMIDI on desktop and laptop computers (Apple desktop OS, Windows, Linux) but iPads unfortunately lack this support.

# Heroku Deployment

This application can be deployed to any platform that supports python and django. [Heroku](https://heroku.com/) is one such platform, a cloud platform as a service provider (PaaS) that provides for easy deployments from GitHub.

Create a Heroku app. Deploy from the desired branch of this Github repository; the Python buildpack and the Heroku Postgres add-on will be supplied on the basis of the Procfile and runtime files.

Add the following **Config Variables** on the Settings page:

```
SECRET_KEY = YOUR_RANDOM_LONG_PASSWORD
DJANGO_SETTINGS_MODULE = harmony.settings.heroku
ALLOWED_HOSTS = ["myanalyticpianourl.com"]
```

Note that automatic deployments are good for testing but these should be disabled when the site is in active use.

To manage the app via the Heroku CLI and to and create an admin account for the database, use these terminal commands:

```bash
$ heroku login # one-time setup
$ heroku apps # view app names for your login
$ heroku run python manage.py migrate --app HEROKU_APP_NAME
$ heroku run python manage.py createsuperuser --app HEROKU_APP_NAME
```

# Running Locally on Linux

- Requires [Python 3.6.x](http://python.org/downloads/) and [Pip](http://www.pip-installer.org/) to install.
- To install Pip, see [their instructions](http://www.pip-installer.org/en/latest/installing.html).

Run the app locally for the first time as follows:

```sh
$ mkdir AnalyticPiano && cd AnalyticPiano
$ git clone --single-branch --branch GITHUB_BRANCH_NAME https://github.com/ospreyelm/HarmonyLab.git LOCAL_FOLDER_NAME
$ sudo apt-get install python3-venv   # unless already installed
$ python3 -m venv pianoenv
$ source pianoenv/bin/activate
$ cd LOCAL_FOLDER_NAME
$ pipenv install
$ sudo apt-get install postgresql   # unless already installed
$ sudo apt-get install python-psycopg2   # unless already installed
$ sudo apt-get install libpq-dev   # unless already installed
$ export DJANGO_SETTINGS_MODULE="harmony.settings.local"  # multiple local clones will use the same database!
$ ./manage.py makemigrations   # not always necessary
$ ./manage.py migrate
$ ./manage.py createsuperuser   # optional: create admin account
$ ./manage.py runserver
```

Use app! Open `http://127.0.0.1:8000` in a browser, per terminal instructions.

```sh
$ deactivate
```

On subsequent occasions:

```sh
$ cd AnalyticPiano/LOCAL_FOLDER_NAME && source pianoenv/bin/activate && export DJANGO_SETTINGS_MODULE="harmony.settings.local" && ./manage.py runserver
```
