import hashlib
import hmac


def verify_hmac_signature(raw_body, provided_signature, secret):
    if not provided_signature or not secret:
        return False
    digest = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, str(provided_signature).strip())

