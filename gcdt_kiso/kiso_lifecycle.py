# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import os
import imp
import logging
import signal
import sys
import json
from logging.config import dictConfig

import botocore.session
from docopt import docopt

from gcdt.utils import GracefulExit, signal_handler
from gcdt import gcdt_signals
from gcdt.gcdt_awsclient import AWSClient
from gcdt.gcdt_cmd_dispatcher import cmd, get_command
from gcdt.gcdt_logging import logging_config
from gcdt.gcdt_plugins import load_plugins
from gcdt.gcdt_signals import check_hook_mechanism_is_intact, \
    check_register_present
from gcdt.utils import get_context, are_credentials_still_valid, \
    get_env

log = logging.getLogger(__name__)


def _load_hooks(path):
    """Load hook module and register signals.

    :param path: Absolute or relative path to module.
    :return: module
    """
    module = imp.load_source(os.path.splitext(os.path.basename(path))[0], path)
    if not check_hook_mechanism_is_intact(module):
        # no hooks - do nothing
        log.debug('No valid hook configuration: \'%s\'. Not using hooks!', path)
    else:
        if check_register_present(module):
            # register the template hooks so they listen to gcdt_signals
            module.register()
    return module


# lifecycle implementation adapted from
# https://github.com/finklabs/aws-deploy/blob/master/aws_deploy/tool.py
def lifecycle(awsclient, env, tool, command, arguments):
    """Tool lifecycle which provides hooks into the different stages of the
    command execution. See signals for hook details.
    """
    # TODO: remove all these lines
    #         log.error(context['error'])

    log.debug('### init')
    load_plugins()
    load_plugins('gcdttool10')
    context = get_context(awsclient, env, tool, command, arguments)
    # every tool needs a awsclient so we provide this via the context
    context['_awsclient'] = awsclient
    log.debug('### context:')
    log.debug(context)
    if 'error' in context:
        # no need to send an 'error' signal here
        return 1

    ## initialized
    gcdt_signals.initialized.send(context)
    log.debug('### initialized')
    if 'error' in context:
        log.error(context['error'])
        return 1

    # config is "assembled" by config_reader NOT here!
    config = {}

    gcdt_signals.config_read_init.send((context, config))
    log.debug('### config_read_init')
    gcdt_signals.config_read_finalized.send((context, config))
    log.debug('### config_read_finalized')

    # check_credentials
    gcdt_signals.check_credentials_init.send((context, config))
    log.debug('### check_credentials_init')
    gcdt_signals.check_credentials_finalized.send((context, config))
    log.debug('### check_credentials_finalized')
    if 'error' in context:
        log.error(context['error'])
        gcdt_signals.error.send((context, config))
        return 1

    ## lookup
    # gcdt_signals.lookup_init.send((context, config))
    # log.debug('### lookup_init')
    # gcdt_signals.lookup_finalized.send((context, config))
    # log.debug('### lookup_finalized')
    # log.debug('### config after lookup:')
    # log.debug(json.dumps(config))

    ## config validation
    gcdt_signals.config_validation_init.send((context, config))
    log.debug('### config_validation_init')
    gcdt_signals.config_validation_finalized.send((context, config))

    log.debug('### config_validation_finalized')
    if 'error' in context:
        gcdt_signals.error.send((context, config))
        return 1

    ## check credentials are valid (AWS services)
    # DEPRECATED, use gcdt-awsume plugin instead
    # TODO use context expiration
    if are_credentials_still_valid(awsclient):
        context['error'] = \
            'Your credentials have expired... Please renew and try again!'
        log.error(context['error'])
        gcdt_signals.error.send((context, config))
        return 1

    ## bundle step
    gcdt_signals.bundle_pre.send((context, config))
    log.debug('### bundle_pre')
    gcdt_signals.bundle_init.send((context, config))
    log.debug('### bundle_init')
    gcdt_signals.bundle_finalized.send((context, config))
    log.debug('### bundle_finalized')
    if 'error' in context:
        log.error(context['error'])
        gcdt_signals.error.send((context, config))
        return 1

    ## dispatch command providing context and config (= tooldata)
    gcdt_signals.command_init.send((context, config))
    log.debug('### command_init')
    try:
        exit_code = cmd.dispatch(arguments,
                                 context=context,
                                 config=config)
    except GracefulExit:
        raise
    except Exception as e:
        log.exception(e)
        log.debug(str(e), exc_info=True)  # this adds the traceback
        context['error'] = str(e)
        log.error(context['error'])
        exit_code = 1
    if exit_code:
        if 'error' not in context or context['error'] == '':
            context['error'] = '\'%s\' command failed with exit code 1' % command
        gcdt_signals.error.send((context, config))
        return 1

    # gcdt_signals.command_finalized.send((context, config))
    # log.debug('### command_finalized')

    # TODO reporting (in case you want to get a summary / output to the user)

    gcdt_signals.finalized.send(context)
    log.debug('### finalized')
    return 0


def main(doc, tool, dispatch_only=None):
    """gcdt tools parametrized main function to initiate gcdt lifecycle.

    :param doc: docopt string
    :param tool: gcdt tool (gcdt, kumo, tenkai, ramuda, yugen)
    :param dispatch_only: list of commands which do not use gcdt lifecycle
    :return: exit_code
    """
    # Use signal handler to throw exception which can be caught to allow
    # graceful exit.
    # here: https://stackoverflow.com/questions/26414704/how-does-a-python-process-exit-gracefully-after-receiving-sigterm-while-waiting
    signal.signal(signal.SIGTERM, signal_handler)  # Jenkins
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl-C

    try:
        arguments = docopt(doc, sys.argv[1:])
        command = get_command(arguments)
        # DEBUG mode (if requested)
        verbose = arguments.pop('--verbose', False)
        if verbose:
            logging_config['loggers']['gcdt']['level'] = 'DEBUG'
        dictConfig(logging_config)

        if dispatch_only is None:
            dispatch_only = ['version']
        assert tool in ['kiso']

        if command in dispatch_only:
            # handle commands that do not need a lifecycle
            # Note: `dispatch_only` commands do not have a check for ENV variable!
            return cmd.dispatch(arguments)
        else:
            env = get_env()
            if not env:
                log.error('\'ENV\' environment variable not set!')
                return 1

            awsclient = AWSClient(botocore.session.get_session())
            return lifecycle(awsclient, env, tool, command, arguments)
    except GracefulExit as e:
        log.info('Received %s signal - exiting command \'%s %s\'',
                 str(e), tool, command)
        return 1
