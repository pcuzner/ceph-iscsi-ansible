#!/usr/bin/env python
__author__ = 'pcuzner@redhat.com'


import os
import logging

from logging.handlers import RotatingFileHandler
from ansible.module_utils.basic import *

from ceph_iscsi_config.gateway import GWTarget
from ceph_iscsi_config.utils import valid_ip


def main():
    # Configures the gateway on the host. All images defined are added to
    # the default tpg for later allocation to clients
    fields = {"gateway_iqn": {"required": True, "type": "str"},
              # "iscsi_network": {"required": True, "type": "str"},
              "gateway_ip_list": {"required": True},    # "type": "list"},
              "mode": {
                  "required": True,
                  "choices": ['target', 'map']
                  }
              }

    module = AnsibleModule(argument_spec=fields,
                           supports_check_mode=False)

    gateway_iqn = module.params['gateway_iqn']
    gateway_ip_list = module.params['gateway_ip_list'].split(',')
    mode = module.params['mode']

    if not valid_ip(gateway_ip_list):
        module.fail_json(msg="Invalid gateway IP address(es) provided - port 22 check failed ({})".format(gateway_ip_list))

    logger.info("START - GATEWAY configuration started in mode {}".format(mode))

    gateway = GWTarget(logger, gateway_iqn, gateway_ip_list)

    gateway.manage(mode)

    if gateway.error:
        logger.critical("(main) Gateway creation or load failed, unable to continue")
        module.fail_json(msg="iSCSI gateway creation/load failure ({})".format(gateway.error_msg))


    logger.info("END - GATEWAY configuration complete")
    module.exit_json(changed=gateway.changes_made, meta={"msg": "Gateway setup complete"})


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
