#!/usr/bin/env python

__author__ = 'pcuzner@redhat.com'

DOCUMENTATION = """
---
module: igw_purge
short_description: Provide a purge capability to remove an iSCSI gateway environment
description:
  - This module handles the removal of a gateway configuration from a ceph environment.
    The playbook that calls this module prompts the user for the type of purge to perform.
    The purge options are;
    all ... purge all LIO configuration *and* delete all defined rbd images
    lio ... purge only the LIO configuration (rbd's are left intact)

    USE WITH CAUTION

    To support module debugging, this module logs to /var/log/ansible-module-igw_config.log
    on the target machine(s).

option:
  mode:
    description:
      - the mode defines the type of purge requested
        gateway ... remove the LIO configuration only
        disks   ... remove the rbd disks defined to the gateway
    required: true

requirements: ['ceph-iscsi-config', 'python-rtslib']

author:
  - 'Paul Cuzner'

"""

import logging
import socket
import subprocess
import fileinput

from logging.handlers import RotatingFileHandler
from ansible.module_utils.basic import *

from rtslib_fb import root
from rtslib_fb.utils import RTSLibError, RTSLibNotInCFS

import ceph_iscsi_config.settings as settings
from ceph_iscsi_config.common import Config
from ceph_iscsi_config.alua import ALUATargetPortGroup


class LIO(object):
    def __init__(self):
        self.lio_root = root.RTSRoot()
        self.error = False
        self.error_msg = ''
        self.changed = False

    def save_config(self):
        self.lio_root.save_to_file()

    def drop_lun_maps(self, config):

        # disk_keys = config.config['disks'].keys()

        for disk_key in config.config['disks'].keys():

            # pool, image = disk_key.split('/')
            dm_device = config.config['disks'][disk_key]['dm_device']

            for stg_object in self.lio_root.storage_objects:

                if stg_object.name == disk_key:

                    # this is temp until the rtslib lun/backstore deletes the
                    # alua groups for the backstore/lun too.
                    alua_dir = os.path.join(stg_object.path, "alua")

                    for dirname in next(os.walk(alua_dir))[1]:
                        if dirname != "default_tg_pt_gp":
                            try:
                                alua_tpg = ALUATargetPortGroup(stg_object, dirname)
                                alua_tpg.delete()
                            except (RTSLibError, RTSLibNotInCFS) as err:
                                self.error = True
                                self.error_msg = err
                                # fall below. We might be able to clean up still

                    # this is an rbd device that's in the config object, so remove it
                    try:
                        stg_object.delete()
                    except RTSLibError as err:
                        self.error = True
                        self.error_msg = err
                    else:
                        dm_remove_device(dm_device)
                        rbd_path = disk_key.replace('.', '/', 1)
                        rbd_unmap(rbd_path)

                        self.changed = True
                        # update the disk item to remove the wwn information
                        image_metadata = config.config['disks'][disk_key]   # current disk meta data dict
                        image_metadata['wwn'] = ''
                        image_metadata['dm_device'] = ''
                        config.update_item("disks", disk_key, image_metadata)


class Gateway(LIO):

    def __init__(self, config_object):
        LIO.__init__(self)

        self.config = config_object

    def session_count(self):
        return len(list(self.lio_root.sessions))

    def drop_target(self, this_host):
        iqn = self.config.config['gateways'][this_host]['iqn']

        lio_root = root.RTSRoot()
        for tgt in lio_root.targets:
            if tgt.wwn == iqn:
                tgt.delete()
                self.changed = True
                # remove the gateway from the config dict
                self.config.del_item('gateways', this_host)


def dm_remove_device(dm_device):
    rm_ok = True

    try:
        subprocess.check_output("multipath -f {}".format(os.path.basename(dm_device)),
                                shell=True)

    except subprocess.CalledProcessError:
        rm_ok = False

    return rm_ok


def rbd_unmap(rbd_path):

    try:
        subprocess.check_output("rbd unmap {}".format(rbd_path), shell=True)
    except subprocess.CalledProcessError:
        unmap_ok = False
    else:
        unmap_ok = True

        # unmap'd from runtime, now remove from the rbdmap file referenced at boot
        for rbdmap_entry in fileinput.input('/etc/ceph/rbdmap', inplace=True):
            if rbdmap_entry.startswith(rbd_path):
                continue
            print rbdmap_entry.strip()

    return unmap_ok


def delete_group(module, image_list, cfg):

    logger.debug("RBD Images to delete are : {}".format(','.join(image_list)))
    pending_list = list(image_list)

    for rbd_path in image_list:
        if delete_rbd(module, rbd_path):
            disk_key = rbd_path.replace('/', '.', 1)
            cfg.del_item('disks', disk_key)
            pending_list.remove(rbd_path)
            cfg.changed = True

    if cfg.changed:
        cfg.commit()

    return pending_list


def delete_rbd(module, rbd_path):

    logger.debug("issuing delete for {}".format(rbd_path))
    rm_cmd = 'rbd --no-progress rm {}'.format(rbd_path)
    rc, rm_out, err = module.run_command(rm_cmd, use_unsafe_shell=True)
    logger.debug("delete RC = {}, {}".format(rc, rm_out, err))

    return True if rc == 0 else False


def get_update_host(config):
    """
    decide which gateway host should be responsible for any config object updates
    :param config: configuration dict from the rados pool
    :return: a suitable gateway host that is online
    """

    ptr = 0
    potential_hosts = [host_name for host_name in config["gateways"].keys()
                       if isinstance(config["gateways"][host_name], dict)]

    # Assume the 1st element from the list is OK for now
    # TODO check the potential hosts are online/available

    return potential_hosts[ptr]


def ansible_main():

    fields = {"mode": {"required": True,
                       "type": "str",
                       "choices": ["gateway", "disks"]
                       }
              }

    module = AnsibleModule(argument_spec=fields,
                           supports_check_mode=False)

    run_mode = module.params['mode']
    changes_made = False

    logger.info("START - GATEWAY configuration PURGE started, run mode is {}".format(run_mode))
    cfg = Config(logger)
    this_host = socket.gethostname().split('.')[0]

    #
    # Purge gateway configuration, if the config has gateways
    if run_mode == 'gateway' and len(cfg.config['gateways'].keys()) > 0:

        update_host = get_update_host(cfg.config)
        lio = LIO()
        gateway = Gateway(cfg)

        if gateway.session_count() > 0:
            module.fail_json(msg="Unable to purge - gateway still has active sessions")

        gateway.drop_target(this_host)
        if gateway.error:
            module.fail_json(msg=gateway.error_msg)

        lio.drop_lun_maps(cfg)
        if lio.error:
            module.fail_json(msg=lio.error_msg)

        if gateway.changed or lio.changed:

            if this_host == update_host:
                cfg.reset = True
                gw_keys = cfg.config["gateways"].keys()
                for key in gw_keys:
                    cfg.del_item("gateways", key)

                client_names = cfg.config["clients"].keys()
                for client in client_names:
                    cfg.del_item("clients", client)

                cfg.commit()

            lio.save_config()
            changes_made = True

    elif run_mode == 'disks' and len(cfg.config['disks'].keys()) > 0:
        #
        # Remove the disks on this host, that have been registered in the config object
        #
        # if the owner field for a disk is set to this host, this host can safely delete it
        # nb. owner gets set at rbd allocation and mapping time
        images_left = []

        # delete_list will contain a list of pool/image names where the owner is this host
        delete_list = [key.replace('.', '/', 1) for key in cfg.config['disks']
                       if cfg.config['disks'][key]['owner'] == this_host]

        if delete_list:
            images_left = delete_group(module, delete_list, cfg)

        # if the delete list still has entries we had problems deleting the images
        if images_left:
            module.fail_json(msg="Problems deleting the following rbd's : {}".format(','.join(images_left)))

        changes_made = cfg.changed

        logger.debug("ending lock state variable {}".format(cfg.config_locked))

    logger.info("END   - GATEWAY configuration PURGE complete")

    module.exit_json(changed=changes_made, meta={"msg": "Purge of iSCSI settings ({}) complete".format(run_mode)})

if __name__ == '__main__':

    module_name = os.path.basename(__file__).replace('ansible_module_', '')
    logger = logging.getLogger(os.path.basename(module_name))
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler('/var/log/ansible-module-igw_config.log',
                                  maxBytes=5242880,
                                  backupCount=7)
    log_fmt = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s : %(message)s')
    handler.setFormatter(log_fmt)
    logger.addHandler(handler)

    settings.init()

    ansible_main()
