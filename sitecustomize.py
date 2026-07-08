try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import ssl
if hasattr(ssl, 'VERIFY_X509_STRICT'):
    # Zscaler (and some other corporate CA) certificates do not mark
    # Basic Constraints as critical, which OpenSSL 3.x / Python 3.12+
    # rejects under VERIFY_X509_STRICT.  Patch the default context
    # factory so all SSL connections in this interpreter are lenient
    # about that specific constraint.
    _orig_create_default_context = ssl.create_default_context

    def _create_default_context(*args, **kwargs):
        ctx = _orig_create_default_context(*args, **kwargs)
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return ctx

    ssl.create_default_context = _create_default_context
