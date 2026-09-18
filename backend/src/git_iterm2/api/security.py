import hmac
import logging

from aiohttp import web
from aiohttp.typedefs import Handler

from git_iterm2.api.keys import CONFIG_KEY
from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.models import ErrorBody

logger = logging.getLogger(__name__)

STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.NOT_A_REPO: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.LOCKED: 423,
    ErrorCode.DIRTY_TREE: 409,
    ErrorCode.NON_FAST_FORWARD: 409,
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.INVALID_PATH: 400,
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.UNSUPPORTED: 501,
    ErrorCode.GIT_FAILED: 500,
    ErrorCode.STALE_CURSOR: 409,
}


def error_response(error: GitError) -> web.Response:
    body = ErrorBody.from_error(error)
    return web.Response(
        status=STATUS_BY_CODE[error.code],
        text=body.model_dump_json(),
        content_type="application/json",
    )


def _local_port(request: web.Request) -> int | None:
    transport = request.transport
    if transport is None:
        return None
    sockname = transport.get_extra_info("sockname")
    return int(sockname[1]) if sockname else None


def _content_security_policy(host: str) -> str:
    return (
        "default-src 'self'; "
        f"connect-src 'self' ws://{host}; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'"
    )


@web.middleware
async def security_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    port = _local_port(request)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if request.host not in allowed_hosts:
        return error_response(GitError(ErrorCode.FORBIDDEN, "Host not allowed"))

    origin = request.headers.get("Origin")
    if origin is not None and origin not in {f"http://{host}" for host in allowed_hosts}:
        return error_response(GitError(ErrorCode.FORBIDDEN, "Origin not allowed"))

    if request.path.startswith("/api/"):
        token = request.app[CONFIG_KEY].token
        provided = request.headers.get("X-Token", "")
        if not hmac.compare_digest(provided.encode("utf-8", "surrogateescape"), token.encode()):
            return error_response(GitError(ErrorCode.UNAUTHORIZED, "Missing or invalid token"))

    response = await handler(request)
    if not response.prepared:
        response.headers["Content-Security-Policy"] = _content_security_policy(request.host)
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@web.middleware
async def error_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        return await handler(request)
    except GitError as error:
        return error_response(error)
    except web.HTTPException as http_error:
        if http_error.status < 400 or http_error.status >= 500:
            raise
        body = ErrorBody(code=ErrorCode.INVALID_ARGUMENT, message=http_error.reason)
        return web.Response(
            status=http_error.status,
            text=body.model_dump_json(),
            content_type="application/json",
        )
    except Exception:
        logger.exception("unhandled error")
        body = ErrorBody(code=ErrorCode.GIT_FAILED, message="Internal error")
        return web.Response(
            status=500, text=body.model_dump_json(), content_type="application/json"
        )
