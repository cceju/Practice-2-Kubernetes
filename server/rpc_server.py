from collections.abc import Callable
from typing import Any

class ErrorCode:
    """
    Protocol error codes
    """

    PROCEDURE_NOT_FOUND = "PROCEDURE_NOT_FOUND"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    BAD_MESSAGE = "BAD_MESSAGE"

class RPCServer:
    """
    Holds the procedure table and dispatches requests
    """

    def __init__(self):
        self._procedures: dict[str, Callable[..., Any]] = {}

    def procedures(self) -> list[str]:
        """
        Names of the registered procedures sorted
        """

        return sorted(self._procedures)

    def register(self, function: Callable[..., Any]) -> None:
        """
        Registers a procedure under a public name

        Args:
            function: Callable implementing the operation

        Raises:
            TypeError: If function is not callable
            ValueError: If the function is already registered
        """

        name = function.__name__
        if not callable(function):
            raise TypeError(f"Procedure {name} is not collable")

        if name in self._procedures:
            raise ValueError(f"Procedure {name} is already registered")

        self._procedures[name] = function

    def dispatch(self, request: dict) -> dict:
        """
        Runs the request and returns the response

        Args:
            request: Deserialized request, with function and args

        Returns:
            Response dictionary, with status either ok or error.
        """

        name = request.get("function")
        args = request.get("args", [])

        function = self._procedures.get(name)
        if function is None:
            return self._error(ErrorCode.PROCEDURE_NOT_FOUND, f"No such procedure {name}")

        try:
            result = function(*args)
        except TypeError as e:
            return self._error(ErrorCode.INVALID_ARGUMENTS, str(e))
        except Exception as e:
            return self._error(ErrorCode.EXECUTION_ERROR, str(e))

        return self._result(result)
    
    @staticmethod
    def _error(code: str, message: str) -> dict:
        """
        Builds an error response in the protocols format
        """

        return {"status": "error", "error": code, "message": message}

    @staticmethod
    def _result(result: str) -> dict:
        """
        Builds a result response in the protocols format
        """

        return {"status": "ok", "result": result}

if __name__ == "__main__":
    from procedures import resize

    rpc = RPCServer()
    rpc.register(resize)

    print(rpc.dispatch({"function": "resize", "args": ["a.jpg", 800, 600]}))
    print(rpc.dispatch({"function": "does_not_exist", "args": []}))
    print(rpc.dispatch({"function": "test", "args": ["a.jpg"]}))
