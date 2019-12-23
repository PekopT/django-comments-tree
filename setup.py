import sys

from setuptools import setup, find_packages
from setuptools.command.test import test

version = {}
with open("django_comments_tree/version.py") as fp:
    exec(fp.read(), version)


def run_tests(*args):
    from django_comments_tree.tests import run_tests
    errors = run_tests()
    if errors:
        sys.exit(1)
    else:
        sys.exit(0)


test.run_tests = run_tests


setup(
    name="django-comments-tree",
    version=version['__version__'],
    packages=find_packages(exclude=['tests']),
    scripts=[],
    include_package_data=True,
    license="MIT",
    description=("Django Comments Framework extension app with django-treebeard "
                 "support, follow up notifications and email "
                 "confirmations, as well as real-time comments using Firebase "
                 "for notifications."),
    long_description=("A reusable Django app that uses django-treebeard "
                      "to create a threaded"
                      "comments Framework, following up "
                      "notifications and comments that only hits the "
                      "database after users confirm them by email."
                      "Real-time comment updates are also available using "
                      "Django channels as a notification mechanism of comment updates. "
                      "Clients can connect to channels for updates, and then query "
                      "the backend for the actual changes, so that all data is "
                      "located in the backend database."
                      ),
    author="Ed Henderson",
    author_email="ed@sharpertool.com",
    maintainer="Ed Henderson",
    maintainer_email="ed@sharpertool.com",
    keywords="django comments treebeard threaded django-channels websockets",
    url="https://github.com/pekopt/django-comments-tree",
    project_urls={
        'Documentation': 'https://django-comments-tree.readthedocs.io/en/latest/',
        'Github': 'https://github.com/pekopt/django-comments-tree',
        'Original Package': 'https://github.com/danirus/django-comments-xtd',
    },
    python_requires='>=3.6',
    install_requires=[
        'Django>=2.0,<3.0',
        'django-treebeard>=4.1.0',
        'djangorestframework>=3.6',
        'draftjs_exporter>=2.1.6',
        'django-markupfield>=1.5',
        'markdown>=3.1.1',
        'docutils',
        'six',
    ],
    extras_requires=[
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Framework :: Django',
        'Natural Language :: English',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary',
    ],
    test_suite="dummy",
    zip_safe=True
)
