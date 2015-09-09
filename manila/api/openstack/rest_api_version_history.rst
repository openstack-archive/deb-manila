REST API Version History
========================

This documents the changes made to the REST API with every
microversion change. The description for each version should be a
verbose one which has enough information to be suitable for use in
user documentation.

1.0
---

  The 1.0 Manila API includes all v1 core APIs existing prior to
  the introduction of microversions.

1.1
---

  This is the initial version of the Manila API which supports
  microversions.

  A user can specify a header in the API request::

    X-OpenStack-Manila-API-Version: <version>

  where ``<version>`` is any valid api version for this API.

  If no version is specified then the API will behave as version 1.0
  was requested.

  The only API change in version 1.1 is versions, i.e.
  GET http://localhost:8786/, which now returns the minimum and
  current microversion values.

1.2
---
  Share create() method doesn't ignore availability_zone field of provided
  share.

1.3
---
  Snapshots become optional and share payload now has
  boolean attr 'snapshot_support'.

1.4
---
  Share instances admin API and update of Admin Actions extension.
