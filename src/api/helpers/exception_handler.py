from __future__ import annotations

from enum import Enum


class ResponseMessage(str, Enum):
    INTERNAL_SERVER_ERROR = "Server might meet some errors. Please try again later !!!"
    SUCCESS = "Process successfully !!!"
    NOT_FOUND = "Resource not found !!!"
    BAD_REQUEST = "Invalid request !!!"
    UNPROCESSABLE_ENTITY = "Input is not allowed !!!"
