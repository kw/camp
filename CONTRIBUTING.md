# Contributing to Camp

Thanks! We could probably use the help.

## Code of Conduct

We'll likely need to establish a formal code of conduct at some point in
the life of this project, but for now, use the following guidelines:

1. If you are working on Camp, it's likely because you are associated with
   a larp that uses or intends to use Camp.
2. That larp probably has their own Code of Conduct.
3. Don't do anything here that would violate your larp's guidelines.
   Any reports of inappropriate behavior will be forwarded to whatever
   larp you're here on behalf of.
4. You should assume that if you receive a ban or long-term suspension
   from a larp working with us, you may receive in-kind treatment here.

Finally, we understand that larp communities can be political and fractuous,
and the project owner(s) and major contributors are unlikely to be immune to
this. If you take issue with the project owner(s), major contributors,
participating larps, or others and your concerns are not adequately addressed,
please feel free to fork this project and run your own version with our blessing.
See the `LICENSE` file for details. It's important to us that every larp
has useful tools to make the lives of their players and staff better, even
if we might come to hate each other's guts down the line.

If you have concerns, please send them to <contact@wizardstower.dev>.

## I have a question or request

Before asking questions, please look through our existing documentation and
the [Issues](https://github.com/kw/camp/issues) list for answers. If you still have questions:

1. Open a [new issue](https://github.com/kw/camp/issues/new).
2. Include as much relevant context about the problem as you can.
3. If you're having problems running the project, include information about
   where and how you're trying to run it (on Windows 95, in Amazon AWS)

We'll take a look at your issue when we can.

## I Want To Contribute

### Legal Notice
When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project license.

### Getting Started

See the [Getting Started](docs/getting-started.md) guide for details on getting up and running.

### Making Contributions

We recommend the following workflow:

1. Create a new branch in your local git clone.
2. Do your development work on the branch.
   Verify that the existing tests pass, and ideally, that you
   have written new tests that also pass.
3. Commit your changes at logical points. Note that, if you
   set up `pre-commit` correctly, it will run and may make
   modifications or simply reject your commit.
4. If `pre-commit` makes changes, you'll need to stage those
   changes and try to commit again. Note that some of `pre-commit`'s
   checks are not things that it automatically fixes, and you'll
   need to figure out what's wrong before committing.
   If you can't figure out what's wrong, use `git commit --no-verify`
   to skip the checks. This will at least let you upload your changes
   so that someone else can look at them.
5. Go to GitHub and create a pull request from your branch. GitHub will
   usually prompt you to do this when you visit.
6. Wait for code reviews. If you get errors from the presubmit services,
   see if you can resolve them. Otherwise, we'll try to assist.
