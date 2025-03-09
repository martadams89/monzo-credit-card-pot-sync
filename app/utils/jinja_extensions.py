"""Custom Jinja extensions."""

import jinja2
from jinja2.ext import Extension
from jinja2.nodes import CallBlock, Const, ContextReference
from jinja2.parser import Parser
import logging

logger = logging.getLogger(__name__)

class TryExtension(Extension):
    """Add a try/except block to Jinja templates."""
    
    tags = {'try'}
    
    def __init__(self, environment):
        super(TryExtension, self).__init__(environment)
        
        # Add the extension to Jinja
        environment.extend(
            try_handlers={}
        )
    
    def parse(self, parser):
        """Parse the try/except block."""
        token = next(parser.stream)
        lineno = token.lineno
        
        # Parse the body of the try block
        body = parser.parse_statements(['name:except', 'name:endtry'], drop_needle=False)
        
        # Check if we hit an except block
        has_except = parser.stream.current.test('name:except')
        
        # If we found an except block, parse it
        if has_except:
            next(parser.stream)  # Consume the 'except' token
            except_body = parser.parse_statements(['name:endtry'], drop_needle=False)
        else:
            except_body = []
        
        # Consume the endtry token
        next(parser.stream)
        
        # Create a call to the try helper function
        call = self.call_method(
            '_try_except',
            [
                ContextReference()
            ],
            lineno=lineno
        )
        
        # Return a block with the try body and possibly the except body
        return CallBlock(
            call,
            [],
            [],
            body if not has_except else except_body
        ).set_lineno(lineno)
    
    def _try_except(self, context, caller):
        """Execute the try/except block."""
        try:
            return caller()
        except Exception as e:
            logger.debug(f"Caught exception in template: {str(e)}")
            return ''


def register_try_except(app):
    """Register the try/except extension with the Flask app."""
    app.jinja_env.add_extension(TryExtension)
    logger.info("Registered TryExtension with Jinja environment")
