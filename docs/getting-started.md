# Getting Started

## Local Development

Unless you're just editing documentation, your first step to contributing is
likely getting the project to run on your machine. Hopefully, the following steps
should get your up and running.

The easiest setup is probably using Docker, which will smooth out most configuration issues.
The instructions below assume you're using this method. If you would prefer to run without
docker, see [Getting Started without Docker](./getting-started-non-docker.md)

### Requirements

* [`pre-commit`](https://pre-commit.com/)
* [Docker for Desktop](https://www.docker.com/products/docker-desktop/)

### Setup

To install the project's development requirements, visit this repo in
your shell and run:

```sh
docker-compose up -d --build
```

This will build and start the container. It may take a while on the first run.

Now, try browsing to http://localhost:8000. If you get an error screen saying

  OperationalError at /
  no such table: game_game

then so far, so good! We just need to populate the database.

You can send commands directly to the container. To run tests, try:

```sh
docker-compose exec web pytest
```

Alternatively, if you plan on issuing several commands, start a shell
directly within the container:

```sh
docker-compose exec web bash
```

#### Stopping the container

Later, when you want to stop the container:
```sh
docker-compose down
```

And repeat `docker-compose up -d --build` to start it back up.

### Django

Camp uses [Django](https://www.djangoproject.com/) as its backend framework.
If you haven't used Django before, the tutorial on their website, or the
[Django Girls tutorial](https://tutorial.djangogirls.org/) are good places
to start. The rest of this document assumes some familiarity.

The command below are all to be run **inside** the container. Either start
a shell in the container using `docker-compose exec web shell` or send them
individually.

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

#### Access the admin panel

By default, the admin panel should be accessible at `/admin` on the server,
so most likely http://127.0.0.1:8000/admin.

### Pre-commit

When it comes time to commit your work, we'll want to check for and automatically
correct some formatting and other issues.

Pre-commit checks are handles by the [`pre-commit`](https://pre-commit.com/)
tool. This will be run outside of your Docker environment.

```sh
pre-commit install
```

You can then manually run pre-commit checks with `pre-commit run`, or just
attempt to commit changes. Pre-commit hooks check for various issues and
in some cases automatically fix them (for example, the Black linter). If
a hook changes any files, your commit will fail. You'll then need to add the
changes to the CL and try committing again.

If you fail to install the pre-commit hooks, the CI system will run it for you
in pull requests. Depending on the failure, it may update the PR for you or
simply provide a failure notice.
