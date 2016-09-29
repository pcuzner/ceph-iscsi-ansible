#!/usr/bin/env python

__author__ = 'pcuzner@redhat.com'

import logging
from logging.handlers import RotatingFileHandler

from ansible.module_utils.basic import *

from ceph_iscsi_config.lun import LUN
from ceph_iscsi_config.utils import valid_size


def main():

    # Define the fields needs to create/map rbd's the the host(s)
    # NB. features and state are reserved/unused
    fields = {
        "pool": {"required": False, "default": "rbd", "type": "str"},
        "image": {"required": True, "type": "str"},
        "size": {"required": True, "type": "str"},
        "host": {"required": True, "type": "str"},
        "features": {"required": False, "type": "str"},
        "state": {
            "default": "present",
            "choices": ['present', 'absent'],
            "type": "str"
        },
    }

    # not supporting check mode currently
    module = AnsibleModule(argument_spec=fields,
                           supports_check_mode=False)

    pool = module.params["pool"]
    image = module.params['image']
    size = module.params['size']
    allocating_host = module.params['host']

    ################################################
    # Validate the parameters passed from Ansible  #
    ################################################
    if not valid_size(size):
        logger.critical("image '{}' has an invalid size specification '{}' in the ansible configuration".format(image,
                                                                                                         size))
        module.fail_json(msg="(main) Unable to use the size parameter '{}' for image '{}' from the playbook - "
                             "must be a number suffixed by M, G or T".format(size, image))

    # define a lun object and perform some initial parameter validation
    lun = LUN(logger, pool, image, size, allocating_host)
    if lun.error:
        module.fail_json(msg=lun.error_msg)

    logger.info("START - LUN configuration started for {}/{}".format(pool, image))

    # attempt to create/allocate the LUN for LIO
    lun.allocate()
    if lun.error:
        module.fail_json(msg=lun.error_msg)

    if lun.num_changes == 0:
        logger.info("END   - No changes needed")
    else:
        logger.info("END   - {} configuration changes made".format(lun.num_changes))

    module.exit_json(changed=(lun.num_changes > 0), meta={"msg": "Configuration updated"})


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

    main()
