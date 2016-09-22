# Environment variables

export MANILA_TEMPEST_COMMIT="c592707"  # 2 Sept, 2016 - tempest 12.2.0

# ----------------------------------------------

# Functions

# Import devstack functions
source $BASE/new/devstack/functions

function manila_check_service_vm_availability {
    # First argument is expected to be IP address of a service VM

    wait_step=10
    wait_timeout=300
    available='false'
    while (( wait_timeout > 0 )) ; do
        if ping -w 1 $1; then
            available='true'
            break
        fi
        ((wait_timeout-=$wait_step))
        sleep $wait_step
    done

    if [[ $available == 'true' ]]; then
        echo "SUCCESS! Service VM $1 is available."
    else
        echo "FAILURE! Service VM $1 is not available."
        exit 1
    fi
}

function manila_wait_for_generic_driver_init {
    # First argument is expected to be file path to Manila config

    MANILA_CONF=$1
    DRIVER_GROUPS=$(iniget $MANILA_CONF DEFAULT enabled_share_backends)
    for driver_group in ${DRIVER_GROUPS//,/ }; do
        SHARE_DRIVER=$(iniget $MANILA_CONF $driver_group share_driver)
        GENERIC_DRIVER='manila.share.drivers.generic.GenericShareDriver'
        DHSS=$(iniget $MANILA_CONF $driver_group driver_handles_share_servers)
        if [[ $SHARE_DRIVER == $GENERIC_DRIVER && $(trueorfalse False DHSS) == False ]]; then
            # Wait for availability
            source /opt/stack/new/devstack/openrc admin demo
            vm_id=$(iniget $MANILA_CONF $driver_group service_instance_name_or_id)
            vm_ips=$(nova show $vm_id | grep "private network")
            attempts=0
            for vm_ip in ${vm_ips//,/ }; do
                # Get IPv4 address
                if [[ $vm_ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                    # Check availability
                    ((attempts++))
                    manila_check_service_vm_availability $vm_ip
                    break
                fi
            done
            if [[ (( attempts < 1 )) ]]; then
                echo "No IPv4 addresses found among private IPs of '$vm_id' for '$GENERIC_DRIVER'. "\
                    "Reported IPs: '$vm_ips'."
                exit 1
            fi
        fi
    done
}

function manila_wait_for_drivers_init {
    # First argument is expected to be file path to Manila config

    manila_wait_for_generic_driver_init $1

    # Sleep to make manila-share service notify manila-scheduler about
    # its capabilities on time.
    sleep 10
}

function archive_file {
    # First argument is expected to be filename
    local filename=$1

    sudo gzip -9 $filename
    sudo chown jenkins:jenkins $filename.gz
    sudo chmod a+r $filename.gz
}

function save_tempest_results {
    # First argument is expected to be number or tempest run

    local src_dirname
    local dst_dirname

    src_dirname="$BASE/new/tempest"
    dst_dirname="$BASE/logs/tempest_$1"

    # 1. Create destination directory
    sudo mkdir $dst_dirname
    sudo chown jenkins:jenkins $dst_dirname
    sudo chmod 755 $dst_dirname

    # 2. Save tempest configuration file
    sudo cp $src_dirname/etc/tempest.conf $dst_dirname/tempest_conf.txt

    # 3. Save tempest log file
    cp $src_dirname/tempest.log $src_dirname/tempest.txt
    echo '' > $src_dirname/tempest.log
    archive_file $src_dirname/tempest.txt
    sudo mv $src_dirname/tempest.txt.gz $dst_dirname/tempest.txt.gz

    # 4. Save tempest testr results

    # Check for an interrupted run first
    if [ -f $src_dirname/.testrepository/tmp* ]; then
        sudo cat $src_dirname/.testrepository/tmp* >> $src_dirname/tempest.subunit
    elif [ -f $src_dirname/.testrepository/0 ]; then
        pushd $src_dirname
        sudo testr last --subunit > $src_dirname/tempest.subunit
        popd
    fi

    if [ -f $src_dirname/tempest.subunit ]; then
        sudo /usr/os-testr-env/bin/subunit2html \
            $src_dirname/tempest.subunit $src_dirname/testr_results.html
        archive_file $src_dirname/tempest.subunit
        sudo mv $src_dirname/tempest.subunit.gz $dst_dirname/tempest.subunit.gz

        archive_file $src_dirname/testr_results.html
        sudo mv $src_dirname/testr_results.html.gz $dst_dirname/testr_results.html.gz

        # 5. Cleanup
        sudo rm -rf $src_dirname/.testrepository
    else
        echo "No 'testr' results available for saving. File '$src_dirname/tempest.subunit' is absent."
    fi
}
