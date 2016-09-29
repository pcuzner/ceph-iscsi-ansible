#!/usr/bin/env python

__author__ = 'pcuzner@redhat.com'


import logging
from logging.handlers import RotatingFileHandler
from ansible.module_utils.basic import *

from ceph_iscsi_config.client import GWClient


def main():

    fields = {
        "client_iqn": {"required": True, "type": "str"},
        "image_list": {"required": True, "type": "str"},
        "credentials": {"required": False, "type": "str", "default": ''},
        "auth": {
            "required": False,
            "default": '',
            "choices": ['', 'chap'],
            "type": "str"
        },
        "state": {
            "required": True,
            "choices": ['present', 'absent'],
            "type": "str"
            },
        }

    module = AnsibleModule(argument_spec=fields,
                           supports_check_mode=False)

    client_iqn = module.params['client_iqn']
    image_list = module.params['image_list'].split(',')
    credentials = module.params['credentials']
    auth_type = module.params['auth']
    desired_state = module.params['state']

    auth_methods = ['chap']

    if auth_type in auth_methods and not credentials:
        module.fail_json(msg="Unable to configure - auth method of '{}' requested, without"
                             " credentials for {}".format(auth_type, client_iqn))

    logger.info("START - Client configuration started : {}".format(client_iqn))

    # The client is defined using the GWClient class. This class handles client attribute updates,
    # rados configuration object updates and LIO settings. Since the logic is external to this
    # custom module, clients can be created/deleted by other methods in the same manner.
    client = GWClient(logger, client_iqn, image_list, auth_type, credentials)

    client.manage(desired_state)

    if client.error:
        module.fail_json(msg=client.error_msg)

    logger.info("END   - Client configuration complete - {} changes made".format(client.change_count))

    changes_made = True if client.change_count > 0 else False

    module.exit_json(changed=changes_made, meta={"msg": "Client definition completed {} "
                                                 "changes made".format(client.change_count)})

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
