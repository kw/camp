# Camp
Larp Campaign Manager

## FAQ
### What is this? Should I care?

A web app intended to help run live action roleplaying games.
Specifically:

* Character management with custom rules engines
* Event scheduling, registration, and payment
* Basic chapter managament (for larps with multiple member chapters)
* Tracking of player information and usage of service points

### Can I use this? Should I?

Camp is in extremely early development and doesn't actually boast any of
the features described above and is not yet suitable for any use.

### Can I contribute?

We aren't accepting external contributions at this time, but thanks!
Keep an eye on this space, contributions will be welcome in the future.

## Local Development

### Requirements

* Python 3.10
* [Pipenv](https://pypi.org/project/pipenv/)
  * The recommended command to install this is `pip install --user pipenv`

### Setup

To install the project's development requirements, visit this repo in
your shell and run:

```sh
pipenv install -d
```

Or, if there's a problem finding the pipenv executable, you could try:

```sh
python3 -m pipenv install -d
```

Once your pipenv environment is installed, use:

```sh
pipenv shell
```

To work inside the virtual environment. For more information on what this means,
see https://pipenv.pypa.io.

### Setup and Run Django

Camp uses [Django](https://www.djangoproject.com/) as its backend framework.
If you haven't used Django before, the tutorial on their website, or the
[Django Girls tutorial](https://tutorial.djangogirls.org/) are good places
to start. The rest of this document assumes some familiarity.

#### Create or upgrade the database

Once inside your `pipenv shell`, you should be able to perform the initial Django
migration to create a local database file by running:

```sh
./manage.py migrate
```

This will create a local SQLite3 database called `db.sqlite3`. You can delete
this to completely reset the state of your database, though this also includes
any user accounts you've created locally.

#### Create an Admin User

To create an admin user:

```sh
./manage.py createsuperuser
```

Should you forget the password you created, use `./manage.py changepassword`.

#### Run the server!

To run a local development server:

```sh
./manage.py runserver
```

This should print out a URL to visit. Do so, and you should be greeted with
a simple homepage with at least a menu for logging in. While the app supports
social auth with (at time of writing) Google and Discord accounts, this requires
some setup to enable, so these will not function locally by default. Instead,
you should be able to user the admin user you created earlier, or sign up to
create another user.

#### Access the admin panel

By default, the admin panel should be accessible at `/admin` on the server,
so most likely http://127.0.0.1:8000/admin.
