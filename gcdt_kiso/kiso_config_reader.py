# -*- coding: utf-8 -*-
"""A gcdt-plugin which demonstrates how to implement hello world as plugin."""
from __future__ import unicode_literals, print_function
import os
import imp
import json

import ruamel.yaml as yaml
from gcdt import gcdt_signals
from gcdt.utils import dict_merge
from gcdt.gcdt_logging import getLogger
from gcdt.gcdt_signals import check_hook_mechanism_is_intact, \
    check_register_present
from gcdt.gcdt_defaults import CONFIG_READER_CONFIG
from gcdt.utils import GracefulExit


log = getLogger(__name__)


def _read_json_cfg(filename):
    # helper
    with open(filename, 'r') as jfile:
        return json.load(jfile)


def read_config(params):
    """Read config from file.
    :param params: context, config (context - the _awsclient, etc..
                   config - The stack details, etc..)
    """
    context, config = params
    try:
        cfg = _read_json_cfg('kiso.json')
        if cfg:
            dict_merge(config, cfg)

    except GracefulExit:
        raise
    except Exception as e:
        config['error'] = e.message
