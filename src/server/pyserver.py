from pygls.server import LanguageServer
from lsprotocol.types import InitializeParams, WorkspaceConfigurationParams, ConfigurationItem
from CodeStyle.CodeStyle import start_formatting

import logging

# Configure logging
logging.basicConfig(
    filename="server.log",  # Log file name
    filemode="a",  # Append to the log file
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG  # Change to INFO or WARNING if needed
)

server = LanguageServer("javaStyleServer", "0.0.1")

@server.command("format_code")
async def format_code(ls: LanguageServer, params):
    #logging.info(f"Received code to format: {params[0]}") # Uncomment to log the code to format
    code = params[0]
    formatted_code, errors = start_formatting(code)
    return {"formatted_code": formatted_code, "errors": errors}

if __name__ == "__main__":
    server.start_io()