..
      Copyright 2010-2011 United States Government as represented by the
      Administrator of the National Aeronautics and Space Administration.
      All Rights Reserved.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

Setting Up a Development Environment
====================================

This page describes how to setup a working Python development
environment that can be used in developing manila on Ubuntu, Fedora or
Mac OS X. These instructions assume you're already familiar with
git. Refer to GettingTheCode_ for additional information.

.. _GettingTheCode: http://wiki.openstack.org/GettingTheCode

Following these instructions will allow you to run the manila unit
tests. If you want to be able to run manila (i.e., create NFS/CIFS shares),
you will also need to install dependent projects: Nova, Neutron, Cinder and Glance.
For this purpose 'devstack' project can be used (A documented shell script to build complete OpenStack development environments).

.. _DeployOpenstack: http://devstack.org/

Virtual environments
--------------------

Manila development uses `virtualenv <http://pypi.python.org/pypi/virtualenv>`__ to track and manage Python
dependencies while in development and testing. This allows you to
install all of the Python package dependencies in a virtual
environment or "virtualenv" (a special subdirectory of your manila
directory), instead of installing the packages at the system level.

.. note::

   Virtualenv is useful for running the unit tests, but is not
   typically used for full integration testing or production usage.

Linux Systems
-------------

.. note::

  This section is tested for manila on Ubuntu (12.04-64) and
  Fedora-based (RHEL 6.1) distributions. Feel free to add notes and
  change according to your experiences or operating system.

Install the prerequisite packages.

On Ubuntu::

  sudo apt-get install python-dev libssl-dev python-pip git-core libmysqlclient-dev libpq-dev

On Fedora-based distributions (e.g., Fedora/RHEL/CentOS/Scientific Linux)::

  sudo yum install python-devel openssl-devel python-pip git libmysqlclient-dev libqp-dev


Mac OS X Systems
----------------

Install virtualenv::

    sudo easy_install virtualenv

Check the version of OpenSSL you have installed::

    openssl version

If you have installed OpenSSL 1.0.0a, which can happen when installing a
MacPorts package for OpenSSL, you will see an error when running
``manila.tests.auth_unittest.AuthTestCase.test_209_can_generate_x509``.

The stock version of OpenSSL that ships with Mac OS X 10.6 (OpenSSL 0.9.8l)
or Mac OS X 10.7 (OpenSSL 0.9.8r) works fine with manila.


Getting the code
----------------
Grab the code::

    git clone https://github.com/openstack/manila.git
    cd manila


Running unit tests
------------------
The unit tests will run by default inside a virtualenv in the ``.venv``
directory. Run the unit tests by doing::

    ./run_tests.sh

The first time you run them, you will be asked if you want to create a virtual
environment (hit "y")::

    No virtual environment found...create one? (Y/n)

See :doc:`unit_tests` for more details.

.. _virtualenv:

Manually installing and using the virtualenv
--------------------------------------------

You can manually install the virtual environment instead of having
``run_tests.sh`` do it for you::

  python tools/install_venv.py

This will install all of the Python packages listed in the
``requirements.txt`` file into your virtualenv. There will also be some
additional packages (pip, distribute, greenlet) that are installed
by the ``tools/install_venv.py`` file into the virtualenv.

If all goes well, you should get a message something like this::

  Manila development environment setup is complete.

To activate the manila virtualenv for the extent of your current shell session
you can run::

     $ source .venv/bin/activate

Or, if you prefer, you can run commands in the virtualenv on a case by case
basis by running::

     $ tools/with_venv.sh <your command>

Contributing Your Work
----------------------

Once your work is complete you may wish to contribute it to the project.  Add
your name and email address to the ``Authors`` file, and also to the ``.mailmap``
file if you use multiple email addresses. Your contributions can not be merged
into trunk unless you are listed in the Authors file. Manila uses the Gerrit
code review system. For information on how to submit your branch to Gerrit,
see GerritWorkflow_.

.. _GerritWorkflow: http://docs.openstack.org/infra/manual/developers.html#development-workflow
