# Getting Started

## Local Development

Unless you're just editing documentation, your first step to contributing is
likely getting the project to run on your machine. Hopefully, the following steps
should get your up and running.

### Requirements

* Python 3.11
* [Poetry](https://python-poetry.org/docs/#installation) package manager
* **Mac**
  * X Code, possibly Homebrew
* **Windows**
  * [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

### Setup

To install the project's development requirements, visit this repo in
your shell and run:

```sh
poetry install
```

Or, if there's a problem finding the poetry executable, you could try:

```sh
python3 -m poetry install
```

Once your poetry environment is installed, use:

```sh
poetry shell
```

To work inside the virtual environment. For more information on what this means,
see https://python-poetry.org/docs/cli/#shell.

#### Pre-commit

Pre-commit checks are handles by the [`pre-commit`](https://pre-commit.com/)
tool. The tool should already be installed in your poetry environment, but to
automatically run it on commit, you must hook it into your local repository:

```sh
pre-commit install
```

You can then manually run pre-commit checks with `pre-commit run`, or just
attempt to commit changes. Pre-commit hooks check for various issues and
in some cases automatically fix them (for example, the Black linter). If
a hook changes any files, your commit will fail and will need to be tried again.

If you fail to install the pre-commit hooks, the CI system will run it for you
in pull requests.

### Django

Camp uses [Django](https://www.djangoproject.com/) as its backend framework.
If you haven't used Django before, the tutorial on their website, or the
[Django Girls tutorial](https://tutorial.djangogirls.org/) are good places
to start. The rest of this document assumes some familiarity.

#### Create or upgrade the database

Once inside your `poetry shell`, you should be able to perform the initial Django
migration to create a local database file by running:

```sh
./manage.py migrate
```

This will create a local SQLite3 database called `db.sqlite3`. You can delete
this to completely reset the state of your database, though this also includes
any user accounts you've created locally.

#### Collect Static Assets

Before running tests, you may need to run collectstatic. This will
compile static assets from around the project into a `staticfiles`
directory.

```sh
./manage.py collectstatic
```

#### Run Tests

Run all Django tests in the project.

```sh
pytest
```

To write your own tests, put them in the `tests` subtree
in a module whose name starts with `test_`. See
[Testing in Django](https://docs.djangoproject.com/en/4.1/topics/testing/)
for details on testing Django projects, and [pytest](https://pytest.org)
for more about the pytest test runner.

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
