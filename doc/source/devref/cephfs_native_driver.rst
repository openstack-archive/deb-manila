..
      Copyright 2016 Red Hat, Inc.
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

CephFS Native driver
====================

The CephFS Native driver enables manila to export shared filesystems to guests
using the Ceph network protocol.  Guests require a Ceph client in order to
mount the filesystem.

Access is controlled via Ceph's cephx authentication system.  When a user
requests share access for an ID, Ceph creates a corresponding Ceph auth ID
and a secret key, if they do not already exist, and authorizes the ID to access
the share.  The client can then mount the share using the ID and the secret
key.

To learn more about configuring Ceph clients to access the shares created
using this driver, please see the Ceph documentation(
http://docs.ceph.com/docs/master/cephfs/).  If you choose to use the kernel
client rather than the FUSE client, the share size limits set in manila
may not be obeyed.

Supported Operations
--------------------

The following operations are supported with CephFS backend:

- Create/delete CephFS share
- Allow/deny CephFS share access

  * Only ``cephx`` access type is supported for CephFS protocol.
  * ``read-only`` access level is supported in Newton or later versions
    of manila.
  * ``read-write`` access level is supported in Mitaka or later versions
    of manila.

- Extend/shrink share
- Create/delete snapshot
- Create/delete consistency group (CG)
- Create/delete CG snapshot

Prerequisites
-------------

- Mitaka or later versions of manila.
- Jewel or later versions of Ceph.
- A Ceph cluster with a filesystem configured (
  http://docs.ceph.com/docs/master/cephfs/createfs/)
- ``ceph-common`` package installed in the servers running the
  :term:`manila-share` service.
- Ceph client installed in the guest, preferably the FUSE based client,
  ``ceph-fuse``.
- Network connectivity between your Ceph cluster's public network and the
  servers running the :term:`manila-share` service.
- Network connectivity between your Ceph cluster's public network and guests.

.. important:: A manila share backed onto CephFS is only as good as the
               underlying filesystem.  Take care when configuring your Ceph
               cluster, and consult the latest guidance on the use of
               CephFS in the Ceph documentation (
               http://docs.ceph.com/docs/master/cephfs/)

Authorize the driver to communicate with Ceph
---------------------------------------------

Run the following commands to create a Ceph identity for manila to use:

.. code-block:: console

    read -d '' MON_CAPS << EOF
    allow r,
    allow command "auth del",
    allow command "auth caps",
    allow command "auth get",
    allow command "auth get-or-create"
    EOF

    ceph auth get-or-create client.manila -o manila.keyring \
    mds 'allow *' \
    osd 'allow rw' \
    mon "$MON_CAPS"


``manila.keyring``, along with your ``ceph.conf`` file, will then need to be
placed on the server running the :term:`manila-share` service.

Enable snapshots in Ceph if you want to use them in manila:

.. code-block:: console

    ceph mds set allow_new_snaps true --yes-i-really-mean-it

In the server running the :term:`manila-share` service, you can place the
``ceph.conf`` and ``manila.keyring`` files in the /etc/ceph directory.  Set the
same owner for the :term:`manila-share` process and the ``manila.keyring``
file.  Add the following section to the ``ceph.conf`` file.

.. code-block:: ini

    [client.manila]
    client mount uid = 0
    client mount gid = 0
    log file = /opt/stack/logs/ceph-client.manila.log
    admin socket = /opt/stack/status/stack/ceph-$name.$pid.asok
    keyring = /etc/ceph/manila.keyring

It is advisable to modify the Ceph client's admin socket file and log file
locations so that they are co-located with manila services's pid files and
log files respectively.


Configure CephFS backend in manila.conf
---------------------------------------

Add CephFS to ``enabled_share_protocols`` (enforced at manila api layer).  In
this example we leave NFS and CIFS enabled, although you can remove these
if you will only use CephFS:

.. code-block:: ini

    enabled_share_protocols = NFS,CIFS,CEPHFS

Create a section like this to define a CephFS backend:

.. code-block:: ini

    [cephfs1]
    driver_handles_share_servers = False
    share_backend_name = CEPHFS1
    share_driver = manila.share.drivers.cephfs.cephfs_native.CephFSNativeDriver
    cephfs_conf_path = /etc/ceph/ceph.conf
    cephfs_auth_id = manila
    cephfs_cluster_name = ceph
    cephfs_enable_snapshots = True

Set ``cephfs_enable_snapshots`` to True in the section to let the driver
perform snapshot related operations.

Then edit ``enabled_share_backends`` to point to the driver's backend section
using the section name.  In this example we are also including another backend
("generic1"), you would include whatever other backends you have configured.


.. code-block:: ini

    enabled_share_backends = generic1, cephfs1


Creating shares
---------------

The default share type may have ``driver_handles_share_servers`` set to True.
Configure a share type suitable for cephfs:

.. code-block:: console

     manila type-create cephfstype false

Then create yourself a share:

.. code-block:: console

    manila create --share-type cephfstype --name cephshare1 cephfs 1

Note the export location of the share:

.. code-block:: console

    manila share-export-location-list cephshare1

The export location of the share contains the Ceph monitor (mon) addresses and
ports, and the path to be mounted.  It is of the form,
``{mon ip addr:port}[,{mon ip addr:port}]:{path to be mounted}``


Allowing access to shares
--------------------------

Allow Ceph auth ID ``alice`` access to the share using ``cephx`` access type.

.. code-block:: console

    manila access-allow cephshare1 cephx alice


Mounting shares using FUSE client
---------------------------------

Using the secret key of the authorized ID ``alice`` create a keyring file,
``alice.keyring`` like:

.. code-block:: ini

    [client.alice]
            key = AQA8+ANW/4ZWNRAAOtWJMFPEihBA1unFImJczA==

.. note::

    In Mitaka release, the secret key is not exposed by any manila API.  The
    Ceph storage admin needs to pass the secret key to the guest out of band of
    manila.  You can refer to the link below to see how the storage admin
    could obtain the secret key of an ID.
    http://docs.ceph.com/docs/jewel/rados/operations/user-management/#get-a-user

    Alternatively, the cloud admin can create Ceph auth IDs for each of the
    tenants.  The users can then request manila to authorize the pre-created
    Ceph auth IDs, whose secret keys are already shared with them out of band
    of manila, to access the shares.

    Following is a command that the the cloud admin could run from the
    server running the :term:`manila-share` service to create a Ceph auth ID
    and get its keyring file.

    .. code-block:: console

        ceph --name=client.manila --keyring=/etc/ceph/manila.keyring auth \
        get-or-create client.alice -o alice.keyring

    For more details, please see the Ceph documentation.
    http://docs.ceph.com/docs/jewel/rados/operations/user-management/#add-a-user

Using the mon IP addresses from the share's export location, create a
configuration file, ``ceph.conf`` like:

.. code-block:: ini

    [client]
            client quota = true
            mon host = 192.168.1.7:6789, 192.168.1.8:6789, 192.168.1.9:6789

Finally, mount the filesystem, substituting the filenames of the keyring and
configuration files you just created, and substituting the path to be mounted
from the share's export location:

.. code-block:: console

    sudo ceph-fuse ~/mnt \
    --id=alice \
    --conf=./ceph.conf \
    --keyring=./alice.keyring \
    --client-mountpoint=/volumes/_nogroup/4c55ad20-9c55-4a5e-9233-8ac64566b98c


Known restrictions
------------------

Mitaka release

Consider the driver as a building block for supporting multi-tenant
workloads in the future.  However, it can be used in private cloud
deployments.

- The guests have direct access to Ceph's public network.

- The secret-key of a Ceph auth ID required to mount a share is not exposed to
  an user by a manila API.  To workaround this, the storage admin would need to
  pass the key out of band of manila, or the user would need to use the Ceph ID
  and key already created and shared with her by the cloud admin.

- The snapshot support of the driver is disabled by default.
  ``cephfs_enable_snapshots`` configuration option needs to be set to ``True``
  to allow snapshot operations.

- Snapshots are read-only.  A user can read a snapshot's contents from the
  ``.snap/{manila-snapshot-id}_{unknown-id}`` folder within the mounted
  share.

- To restrict share sizes, CephFS uses quotas that are enforced in the client
  side.  The CephFS clients are relied on to respect quotas.


Security
--------

Mitaka release

- Each share's data is mapped to a distinct Ceph RADOS namespace.  A guest is
  restricted to access only that particular RADOS namespace.
  http://docs.ceph.com/docs/master/cephfs/file-layouts/

- An additional level of resource isolation can be provided by mapping a
  share's contents to a separate RADOS pool.  This layout would be be preferred
  only for cloud deployments with a limited number of shares needing strong
  resource separation.  You can do this by setting a share type specification,
  ``cephfs:data_isolated`` for the share type used by the cephfs driver.

  .. code-block:: console

       manila type-key cephfstype set cephfs:data_isolated=True

- As mentioned earlier, untrusted manila guests pose security risks to the
  Ceph storage cluster as they would have direct access to the cluster's
  public network.


The :mod:`manila.share.drivers.cephfs.cephfs_native` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: manila.share.drivers.cephfs.cephfs_native
    :noindex:
    :members:
    :undoc-members:
    :show-inheritance:
