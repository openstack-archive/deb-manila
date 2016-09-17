3. Complete the rest of the configuration in ``manila.conf``:

   * In the ``[DEFAULT]`` and ``[oslo_messaging_rabbit]`` sections, configure
     ``RabbitMQ`` message queue access:

     .. code-block:: ini

        [DEFAULT]
        ...
        rpc_backend = rabbit

        [oslo_messaging_rabbit]
        ...
        rabbit_host = controller
        rabbit_userid = openstack
        rabbit_password = RABBIT_PASS

     Replace ``RABBIT_PASS`` with the  password you chose for the ``openstack``
     account in ``RabbitMQ``.

   * In the ``[DEFAULT]`` section, set the following config values:

     .. code-block:: ini

        [DEFAULT]
        ...
        default_share_type = default_share_type
        share_name_template = share-%s
        rootwrap_config = /etc/manila/rootwrap.conf
        api_paste_config = /etc/manila/api-paste.ini

   * In the ``[DEFAULT]`` and ``[keystone_authtoken]`` sections, configure
     Identity service access:

     .. code-block:: ini

        [DEFAULT]
        ...
        auth_strategy = keystone

        [keystone_authtoken]
        ...
        memcached_servers = controller:11211
        auth_uri = http://controller:5000
        auth_url = http://controller:35357
        auth_type = password
        project_domain_id = default
        user_domain_id = default
        project_name = service
        username = manila
        password = MANILA_PASS

     Replace ``MANILA_PASS`` with the password you chose for the ``manila``
     user in the Identity service.

   * In the ``[DEFAULT]`` section, configure the ``my_ip`` option to use the
     management interface IP address of the controller node:

     .. code-block:: ini

        [DEFAULT]
        ...
        my_ip = 10.0.0.11

   * In the ``[oslo_concurrency]`` section, configure the lock path:

     .. code-block:: ini

        [oslo_concurrency]
        ...
        lock_path = /var/lock/manila
