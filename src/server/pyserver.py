from pygls.server import LanguageServer
from lsprotocol.types import InitializeParams, DidChangeConfigurationParams, WorkDoneProgressCreateParams, WorkDoneProgressBegin, WorkDoneProgressReport, ProgressParams, WorkDoneProgressEnd
from CodeStyle import CodeStyle
from CodeSmell import CodeSmell

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
    formatted_code, errors = CodeStyle.start_formatting(code, settings)
    return {"formatted_code": formatted_code, "errors": errors}

@server.command("analyze_smells")
async def analyze_smells(ls: LanguageServer, params):
    token = "analyze_smells"
    ls.lsp.send_request("window/workDoneProgress/create", WorkDoneProgressCreateParams(token=token))

    ls.send_notification("$/progress", ProgressParams(token=token, value=WorkDoneProgressBegin(title="Analyzing code smells", percentage=0, cancellable=False)))

    def progress_callback(percentage):
        ls.send_notification("$/progress", ProgressParams(token=token, value=WorkDoneProgressReport(percentage=percentage)))

    code = params[0]
    smells = await ls.loop.run_in_executor(None, lambda: CodeSmell.start_analysis(code, progress_callback))

    ls.send_notification("$/progress", ProgressParams(token=token, value=WorkDoneProgressEnd()))

    return {"smells": smells}

if __name__ == "__main__":
    server.start_io()