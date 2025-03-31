from pygls.server import LanguageServer
from lsprotocol.types import InitializeParams, DidChangeConfigurationParams, ConfigurationItem
from CodeStyle.CodeStyle import start_formatting

import logging
import os

# Configure logging
logging.basicConfig(
    filename="server.log",  # Log file name
    filemode="a",  # Append to the log file
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG  # Change to INFO or WARNING if needed
)

server = LanguageServer("javaStyleServer", "0.0.1")
settings = {}

@server.feature("initialize")
async def on_initialize(params: InitializeParams):
    global settings
    settings = params.initialization_options

@server.feature("workspace/didChangeConfiguration")
async def on_config_change(params: DidChangeConfigurationParams):
    global settings
    new_settings = params.settings

    if new_settings:
        settings = new_settings

@server.command("format_code")
async def format_code(ls: LanguageServer, params):
    code = params[0]
    formatted_code, errors = start_formatting(code, settings)
    return {"formatted_code": formatted_code, "errors": errors}

if __name__ == "__main__":
    server.start_io()