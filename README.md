# Overview

An Open-Source application for the study of music theory and keyboard skills that takes input from a MIDI keyboard and outputs staff notation. Various analytical vocabularies of melody and harmony are represented. As a practice aid and exercise platform that operates across aural, visual, and tactile domains, this tool accelerates the acquisition of fluency in certain fundamentals of tonal music.

# Quickstart

- Requires [Python 3.6.x](http://python.org/downloads/) and [Pip](http://www.pip-installer.org/) to install. 
- To install Pip, see [their instructions](http://www.pip-installer.org/en/latest/installing.html).

```sh
$ git clone https://github.com/ospreyelm/HarmonyLab.git harmony
$ cd harmony
$ pipenv install
$ ./manage.py migrate
$ ./manage.py runserver
```
You should now be able to run the application on your localhost at ```http://127.0.0.1:8000```. 

# Supported Web Browsers

Chrome is currently the only browser supported, being the single browser that implements the WebMIDI specification.

# Heroku Deployment

This application can be deployed to any platform that supports python and django. One such example is 
[heroku](https://heroku.com/), a cloud platform as a service provider, which makes it easy to deploy changes
directly from the git repository. 

Create a Heroku app with the Python buildpack and the Herok Postgres add-on. Deploy from the desired branch of this Github repository; automatic deploys are good for testing the basic playing interface, but these should be disabled when creating course and exercise data.

The required  **Config Variables** that should be added on the app settings page are as follows:

```
SECRET_KEY = YOUR_RANDOM_LONG_PASSWORD
DJANGO_SETTINGS_MODULE = harmony.settings.heroku
ALLOWED_HOSTS = ["yoururl.com"]
LTI_OAUTH_CREDENTIALS = {"your_lti_key":"your_lti_secret"}
```

To create an admin account for creating course and exercise data, use the Heroku CLI as follows:

```bash
$ heroku login # one-time setup
$ heroku apps # view app names for your login
$ heroku run python manage.py migrate --app HEROKU_APP_NAME
$ heroku run python manage.py createsuperuser --app HEROKU_APP_NAME
```
