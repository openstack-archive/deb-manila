.. _documenting_your_work:

=====================
Documenting your work
=====================


As with most OpenStack services and libraries, manila suffers from appearing
very complicated to understand, develop, deploy, administer and use. As
OpenStack developers working on manila, our responsibility goes beyond
introducing new features and maintaining existing features. We ought to
provide adequate documentation for the benefit of all kinds of audiences. The
guidelines below will explain how you can document (or maintain
documentation for) new (or existing) features and bug fixes in the core manila
project and other projects that are part of the manila suite.


Where to add documentation?
~~~~~~~~~~~~~~~~~~~~~~~~~~~


OpenStack User Guide
--------------------
- Any documentation targeted at end users of manila in OpenStack needs to go
  here. This contains high level information about any feature as long as it
  is available on ``python-manilaclient`` and/or ``manila-ui``.
- If you develop an end user facing feature, you need to provide an
  overview, use cases and example work-flows as part of this documentation.
- **Link**: `User guide <http://docs.openstack.org/user-guide/>`_
- **Repository**: The user guide is maintained within the
  `OpenStack Manuals project <https://github.com/openstack/openstack-manuals>`_


OpenStack Administrator Guide
-----------------------------
- Documentation for administrators of manila deployments in OpenStack clouds
  needs to go here.
- Document instructions for administrators to perform necessary set up
  for utilizing a feature, along with managing and troubleshooting manila
  when the feature is used.
- Relevant configuration options may be mentioned here briefly.
- **Link**: `Administrator guide <http://docs.openstack.org/admin-guide/>`_
- **Repository**: The administrator guide is maintained within the
  `OpenStack Manuals project <https://github.com/openstack/openstack-manuals>`_


OpenStack Configuration Reference
---------------------------------
- Instructions regarding configuration of different manila back ends need to
  be added in this document.
- The configuration reference also contains sections where manila's
  configuration options are auto-documented.
- It contains sample configuration files for using manila with various
  configuration options.
- If you are a driver maintainer, please ensure that your driver and all of
  its relevant configuration is documented here.
- **Link**: `Mitaka release configuration reference
  <http://docs.openstack.org/mitaka/config-reference/>`_
- **Repository**: The configuration reference is maintained within the
  `OpenStack Manuals project <https://github.com/openstack/openstack-manuals>`_


OpenStack Installation Guide
----------------------------
- Instructions regarding setting up manila on OpenStack need to be documented
  here.
- This guide covers step-by-step deployment of OpenStack services using a
  functional example architecture suitable for new users of OpenStack with
  sufficient Linux experience.
- The instructions are written together, but with the help of tags are
  separated out into per-distro installation guides for hosting on the
  documentation website.
- The installation instructions for manila in the Mitaka release lived
  alongside the major projects in the installation guide. However, with the
  Newton release, the install guide will be part of manila's code tree.
- **Links**:

  - `Mitaka installation guide for openSUSE and SLES
    <http://docs.openstack.org/mitaka/install-guide-obs/>`_
  - `Mitaka installation guide for Red Hat Enterprise Linux and CentOS
    <http://docs.openstack.org/mitaka/install-guide-rdo/>`_
  - `Mitaka installation guide for Ubuntu 14.04
    <http://docs.openstack.org/mitaka/install-guide-ubuntu/>`_

- **Repository**: The installation guide is maintained within the
  `OpenStack Manuals project
  <https://github.com/openstack/openstack-manuals>`_. However, with the
  Newton release, manila's install guide will live in its project tree.

.. TODO(gouthamr): add actual links and repo instructions when available.


OpenStack API Reference
-----------------------
- When you add or change a REST API in manila, you will need to add or edit
  descriptions of the API, request and response parameters, microversions and
  expected HTTP response codes as part of the API reference.
- For releases prior to Newton, the API reference was maintained in `Web
  Application Description Language (WADL)
  <https://en.wikipedia.org/wiki/Web_Application_Description_Language>`_
- Starting with the Newton release, manila's API reference will be maintained
  in-tree in custom YAML/JSON format files.
- **Links**:

  - `REST API reference of the Shared File Systems Project v1.0
    <http://developer.openstack.org/api-ref-share-v1.html>`_
  - `REST API reference of the Shared File Systems Project v2.0
    <http://developer.openstack.org/api-ref-share-v2.html>`_

- **Repository**: The API reference is maintained within the
  `OpenStack API Site repository
  <https://github.com/openstack/api-site>`_. However, with the Newton release,
  manila's API reference will live in its project tree.

.. TODO(gouthamr): add actual links and repo instructions when available.


Manila Developer Reference
--------------------------
- When working on a feature in manila, provide judicious inline documentation
  in the form of comments and docstrings. Code is our best developer reference.
- Driver entry-points must be documented with docstrings explaining the
  expected behavior from a driver routine.
- Apart from inline documentation, further developer facing documentation
  will be necessary when you are introducing changes that will affect vendor
  drivers, consumers of the manila database and when building a utility in
  manila that can be consumed by other developers.
- The developer reference for manila is maintained in-tree.
- Feel free to use it as a sandbox for other documentation that does not
  live in manila's code-tree.
- **Link**: `Manila developer reference
  <http://docs.openstack.org/developer/manila/>`_


OpenStack Security Guide
-------------------------
- Any feature that has a security impact needs to be documented here.
- In general, administrators will follow the guidelines regarding best
  practices of setting up their manila deployments with this guide.
- Any changes to ``policy.json`` based authorization, share network related
  security, ``access`` to manila resources, tenant and user related
  information needs to be documented here.
- **Link**: `Security guide <http://docs.openstack.org/security-guide/>`_
- **Repository**: The security guide is maintained within the
  `OpenStack Security-doc project <https://github.com/openstack/security-doc>`_


OpenStack Command Line Reference
--------------------------------
- Help text provided in the ``python-manilaclient`` is extracted into this
  document automatically.
- No manual corrections are allowed on this repository; make necessary
  corrections in the ``python-manilaclient`` repository."
- **Link**: `Manila CLI reference
  <http://docs.openstack.org/cli-reference/manila.html>`_
- **Repository**: The CLI reference is maintained within the
  `OpenStack Manuals project
  <https://github.com/openstack/openstack-manuals>`_.


Important things to note
~~~~~~~~~~~~~~~~~~~~~~~~

- When implementing a new feature, use appropriate
  Commit Message Tags (:ref:`commit_message_tags`).
- Using the ``DocImpact`` flag in particular will create a ``[doc]`` bug
  under the `manila project in launchpad
  <https://bugs.launchpad.net/manila>`_. When your code patch merges, assign
  this bug to yourself and track your documentation changes with it.
- When writing documentation outside of manila, use either a commit message
  header that includes the word ``Manila`` or set the topic of the
  change-set to ``manila-docs``. This will make it easy for manila reviewers
  to find your patches to aid with a technical content review.
- When writing documentation in user/admin/config/api/install guides,
  *always* refer to the project with its service name: ``Shared File Systems
  service`` and not the service type (``share``) or the project name
  (``manila``).
- Follow documentation styles prescribed in the `OpenStack Documentation
  Contributor Guide <http://docs.openstack.org/contributor-guide/>`_. Pay
  heed to the `RST formatting conventions
  <http://docs.openstack.org/contributor-guide/rst-conv.html>`_
  and `Writing style
  <http://docs.openstack.org/contributor-guide/writing-style.html>`_.
- Use CamelCase to spell out `OpenStack` and sentence casing to
  spell out service types, ex: `Shared File Systems service` and lower case
  to spell out project names, ex: `manila` (except when the project name is in
  the beginning of a sentence or a title).
- **ALWAYS** use a first party driver when documenting a feature in the user
  or administrator guides. Provide cross-references to configuration
  reference sections to lead readers to detailed setup instructions for
  these drivers.
- The manila developer reference, the OpenStack user guide, administrator
  reference, API reference and security guide are always *current*, i.e, get
  built with every commit in the respective codebase. Therefore, documentation
  added here need not be backported to previous releases.
- You may backport changes to some documentation such as the configuration
  reference and the installation guide. Refer to the instructions `here
  <http://docs.openstack.org/contributor-guide/additional-git-workflow/
  backport.html>`_.
- **Important "documentation" that isn't really documentation** - ``specs`` and
  ``release notes`` are *NOT* documentation. A specification document is
  written to initiate a dialogue and gather feedback regarding the
  design of a feature. Neither developers nor users will regard a
  specification document as official documentation after a feature has been
  implemented. Release notes (:ref:`adding_release_notes`) allow for
  gathering release summaries and they are not used to understand,
  configure, use or troubleshoot any manila feature.
- **Less is not more, more is more** - Always add detail when possible. The
  health and maturity of our community is reflected in our documentation.
