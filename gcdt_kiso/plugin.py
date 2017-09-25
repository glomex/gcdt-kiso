# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from gcdt import gcdt_signals
from gcdt.gcdt_openapi import get_openapi_defaults, validate_tool_config, \
    incept_defaults_helper, validate_config_helper

from .kiso_config_reader import read_config

from . import read_openapi


# TODO: plugin functionality
# * scaffoling sample-min and sample-max


def incept_defaults(params):
    """incept defaults where needed (after config is read from file).
    :param params: context, config (context - the _awsclient, etc..
                   config - The stack details, etc..)
    """
    incept_defaults_helper(params, read_openapi(), 'kiso')


def validate_config(params):
    """validate the config after lookups.
    :param params: context, config (context - the _awsclient, etc..
                   config - The stack details, etc..)
    """
    context, config = params
    tool = context['tool']
    actual_non_config_command = (context['tool'] == tool and context['command'] in
        config.get(tool, {}).get('defaults', {}).get('non_config_commands', [])
    )

    validate_config_helper(params, read_openapi(), 'kiso')


def register():
    """Please be very specific about when your plugin needs to run and why.
    E.g. run the sample stuff after at the very beginning of the lifecycle
    """
    gcdt_signals.config_read_init.connect(read_config)
    #gcdt_signals.config_read_finalized.connect(incept_defaults)
    #gcdt_signals.config_validation_init.connect(validate_config)


def deregister():
    gcdt_signals.config_read_init.disconnect(read_config)
    #gcdt_signals.config_read_finalized.disconnect(incept_defaults)
    #gcdt_signals.config_validation_init.disconnect(validate_config)
