"""
Patch for the CBOR2 deprecation warning.

This module directly imports from cbor2 to suppress the deprecation warning
that occurs when libraries try to import from the deprecated cbor.decoder module.
"""

import sys
import logging

# Import directly from cbor2 - only import what actually exists in the library
import cbor2
from cbor2.decoder import CBORDecoder  # This exists
from cbor2.types import FrozenDict     # This exists in types module

logger = logging.getLogger(__name__)

def patch_cbor_imports():
    """Patch the sys.modules to redirect cbor.decoder imports to cbor2."""
    # Create a reference to cbor2 in sys.modules
    if 'cbor.decoder' in sys.modules:
        logger.info("Replacing cbor.decoder with cbor2")
        sys.modules['cbor.decoder'] = sys.modules['cbor2']
    if 'cbor.encoder' in sys.modules:
        logger.info("Replacing cbor.encoder with cbor2")
        sys.modules['cbor.encoder'] = sys.modules['cbor2']

# Apply the patch when the module is imported
patch_cbor_imports()
