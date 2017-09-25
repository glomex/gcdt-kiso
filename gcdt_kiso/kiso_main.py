#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The 'kiso' tool is used to deploy infrastructure CloudFormation templates
to AWS cloud.
"""

from __future__ import unicode_literals, print_function
import os
import sys
from collections import OrderedDict
import json
import time
from tempfile import NamedTemporaryFile

from clint.textui import colored
from pyspin.spin import Default, Spinner
from gcdt import utils
from gcdt.gcdt_cmd_dispatcher import cmd
from . import kiso_lifecycle

from gcdt_kumo.kumo_core import load_cloudformation_template, deploy_stack

# creating docopt parameters and usage help
DOC = '''Usage:
        kiso deploy --account-id=<account_id> [--region=<region>] [-v]
        kiso version

-h --help           show this
-v --verbose        show debug messages
'''

def load_template(path):
    """Bail out if template is not found.
    """
    cloudformation, found = load_cloudformation_template(path)
    if not found:
        print(colored.red('could not load cloudformation.py, bailing out...'))
        sys.exit(1)
    return cloudformation


@cmd(spec=['version'])
def version_cmd():
    utils.version()


@cmd(spec=['deploy', '--account-id', '--region'])
def deploy_cmd(account_id, region, override=True, **tooldata):
    context = tooldata.get('context')
    conf = tooldata.get('config')
    awsclient = context.get('_awsclient')

    if region is None:
        region = 'eu-west-1'

    account_cfg = None
    for account in conf['accounts']:
        if account['accountId'] == account_id:
            account_cfg = account

    for stack in account_cfg['stacks']:
        print(stack)
        cloudformation = load_template('%s/cloudformation/cloudformation.py' % stack)
        exit_code = deploy_stack(
            awsclient=awsclient,
            context=context,
            conf=conf,
            cloudformation=cloudformation,
            override_stack_policy=override
        )

        print(exit_code)

    #return exit_code


def main():
    sys.exit(kiso_lifecycle.main(DOC, 'kiso'))


if __name__ == '__main__':
    main()
