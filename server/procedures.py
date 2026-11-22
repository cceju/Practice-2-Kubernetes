import time

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FORMAT = "JPEG"

def image_info(name: str, ) -> dict:
    """
    Returns the metadata of an image

    Args:
        name: Name of the image file

    Returns:
        Dictionary with the filename, dimensions and format.
    """

    return {
        "file": name,
        "width": DEFAULT_WIDTH,
        "height": DEFAULT_HEIGHT,
        "format": DEFAULT_FORMAT,
    }

def grayscale(name: str) -> str:
    """
    Converts an image to grayscale

    Args:
        name: Name of the image file.

    Returns:
        Message describing the result of the processing.
    """

    return f"{name} converted to grayscale"

def resize(name: str, width: int, height: int) -> dict:
    """
    Resizes an image to the given dimensions

    Args:
        name: Name of the image file.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        Dictionary with the file name and the resulting dimensions.
    """

    return {
        "file": name,
        "width": width,
        "height": height,
    }


# --- Basic procedures required by the Practice 1 statement ---------------
# The Practice 1 client (client/client.py) calls these four, so the server
# must expose them for that client to work unchanged.

def add(a, b):
    return a + b


def multiply(a, b):
    return a * b


def power(a, b):
    return a ** b


def slow_task(seconds):
    """Sleeps `seconds` and returns it. Used to test concurrency and load."""
    time.sleep(seconds)
    return seconds
