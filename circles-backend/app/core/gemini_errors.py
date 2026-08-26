from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted


def friendly_gemini_error(e: Exception) -> str:
    """Turn a raw Gemini/API-core exception into a message safe to show users.

    Without this, callers store/return str(e) directly -- for a quota error
    that's a multi-line gRPC status dump, unreadable to a student wondering
    why their upload or quiz generation failed.
    """
    if isinstance(e, ResourceExhausted):
        return (
            "Our AI service has hit its usage limit for now. This usually "
            "resolves within a few minutes to a day -- please try again shortly."
        )
    if isinstance(e, GoogleAPICallError):
        return "Our AI service is temporarily unavailable. Please try again in a few minutes."
    return str(e)
