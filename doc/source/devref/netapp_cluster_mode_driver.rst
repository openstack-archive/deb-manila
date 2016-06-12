..
      Copyright 2014 Mirantis Inc.
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

NetApp Clustered Data ONTAP
===========================

The Shared File Systems service can be configured to use
NetApp Clustered Data ONTAP (cDOT) version 8.2 and later.

Supported Operations
--------------------

The following operations are supported on Clustered Data ONTAP:

- Create CIFS/NFS Share
- Delete CIFS/NFS Share
- Allow NFS Share access

  * IP access type is supported for NFS.
  * Read/write and read-only access are supported for NFS.

- Allow CIFS Share access

  * User access type is supported for CIFS.
  * Read/write access is supported for CIFS.

- Deny CIFS/NFS Share access
- Create snapshot
- Delete snapshot
- Create share from snapshot
- Extend share
- Shrink share
- Manage share
- Unmanage share
- Create consistency group
- Delete consistency group
- Create consistency group from CG snapshot
- Create CG snapshot
- Delete CG snapshot
- Create a replica (DHSS=False)
- Promote a replica (DHSS=False)
- Delete a replica (DHSS=False)
- Update a replica (DHSS=False)
- Create a replicated snapshot (DHSS=False)
- Delete a replicated snapshot (DHSS=False)
- Update a replicated snapshot (DHSS=False)

.. note::

    :term:`DHSS` is abbreviated from `driver_handles_share_servers`.

Supported Operating Modes
-------------------------

The cDOT driver supports both 'driver_handles_share_servers' (:term:`DHSS`)
modes.

If 'driver_handles_share_servers' is True, the driver will create a storage
virtual machine (SVM, previously known as vServers) for each unique tenant
network and provision each of a tenant's shares into that SVM.  This requires
the user to specify both a share network as well as a share type with the DHSS
extra spec set to True when creating shares.

If 'driver_handles_share_servers' is False, the manila admin must configure a
single SVM, along with associated LIFs and protocol services, that will be
used for provisioning shares.  The SVM is specified in the manila config file.

Network approach
----------------

L3 connectivity between the storage cluster and manila host must exist, and
VLAN segmentation may be configured.  All of manila's network plug-ins are
supported with the cDOT driver.

Supported shared filesystems
----------------------------

- NFS (access by IP address or subnet)
- CIFS (authentication by user)

Required licenses
-----------------

- NFS
- CIFS
- FlexClone

Known restrictions
------------------

- For CIFS shares an external Active Directory (AD) service is required. The AD
  details should be provided via a manila security service that is attached to
  the specified share network.
- Share access rules for CIFS shares may be created only for existing users
  in Active Directory.
- The time on external security services and storage must be synchronized. The
  maximum allowed clock skew is 5 minutes.
- cDOT supports only flat and VLAN network segmentation types.

The :mod:`manila.share.drivers.netapp.common.py` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: manila.share.drivers.netapp.common
    :noindex:
    :members:
    :undoc-members:
    :show-inheritance:
