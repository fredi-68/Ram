#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
#
#Monkey patches the logging module to enable
#dictConfig() to deal with positional arguments.
#Cause whoever programmed that library was NOT aware,
#that some handlers need that.

import logging
from logging import config

print("[LogArgFix] Patching position argument support...")

class DictConfigurator(config.DictConfigurator):

    def configure_handler(self, config):

        """
        Configure a handler from a dictionary.
        """

        config_copy = dict(config)  # for restoring in case of error
        formatter = config.pop('formatter', None)
        if formatter:
            try:
                formatter = self.config['formatters'][formatter]
            except Exception as e:
                raise ValueError('Unable to set formatter '
                                 '%r: %s' % (formatter, e))
        level = config.pop('level', None)
        filters = config.pop('filters', None)
        if '()' in config:
            c = config.pop('()')
            if not callable(c):
                c = self.resolve(c)
            factory = c
        else:
            cname = config.pop('class')
            klass = self.resolve(cname)
            #Special case for handler which refers to another handler
            if issubclass(klass, logging.handlers.MemoryHandler) and\
                'target' in config:
                try:
                    th = self.config['handlers'][config['target']]
                    if not isinstance(th, logging.Handler):
                        config.update(config_copy)  # restore for deferred cfg
                        raise TypeError('target not configured yet')
                    config['target'] = th
                except Exception as e:
                    raise ValueError('Unable to set target handler '
                                     '%r: %s' % (config['target'], e))
            elif issubclass(klass, logging.handlers.SMTPHandler) and\
                'mailhost' in config:
                config['mailhost'] = self.as_tuple(config['mailhost'])
            elif issubclass(klass, logging.handlers.SysLogHandler) and\
                'address' in config:
                config['address'] = self.as_tuple(config['address'])
            factory = klass
            
        #Enable position arguments
        args = []
        if "args" in config:
            args = config["args"]
            del config["args"]

        props = config.pop('.', None)
        kwargs = dict([(k, config[k]) for k in config if logging.config.valid_ident(k)])
        try:
            result = factory(*args, **kwargs) #initialize with positional arguments
        except TypeError as te:
            if "'stream'" not in str(te):
                raise
            #The argument name changed from strm to stream
            #Retry with old name.
            #This is so that code can be used with older Python versions
            #(e.g. by Django)
            kwargs['strm'] = kwargs.pop('stream')
            result = factory(**kwargs)
        if formatter:
            result.setFormatter(formatter)
        if level is not None:
            result.setLevel(logging._checkLevel(level))
        if filters:
            self.add_filters(result, filters)
        if props:
            for name, value in props.items():
                setattr(result, name, value)
        return result

logging.config.dictConfigClass = DictConfigurator
print("[LogArgFix] Logging module patch successfull")