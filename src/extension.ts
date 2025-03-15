import * as vscode from "vscode";
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from "vscode-languageclient/node";
import * as path from "path";

interface FormatResponse {
	formatted_code: string;
	errors: string[];
}

let client: LanguageClient | undefined;
let diagCollection: vscode.DiagnosticCollection;

export async function activate(context: vscode.ExtensionContext) : Promise<void> {
	const serverCommand = "python";
    const serverArgs = context.asAbsolutePath(path.join("src", "server", "pyserver.py"));

    let serverOptions: ServerOptions = {
        run: { command: serverCommand, args: [serverArgs], transport: TransportKind.stdio },
        debug: { command: serverCommand, args: [serverArgs], transport: TransportKind.stdio }
    };

    let clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: "java" }],
    };

    client = new LanguageClient("javaStyleServer", "Java Style Server", serverOptions, clientOptions);
    client.start();

	diagCollection = vscode.languages.createDiagnosticCollection("CodeStyleTest");

	const format = vscode.commands.registerCommand('codestyletest.format', async () => {
		const editor = vscode.window.activeTextEditor;
			if (!editor) {
				vscode.window.showErrorMessage("No active text editor found");
				return;
			}
		
		const document = editor.document;
			if (document.languageId !== "java") {
				vscode.window.showErrorMessage("Active document is not a Java file");
				return;
			}
		
		const text = document.getText();

		try {
			const response = await client?.sendRequest("workspace/executeCommand", {
				command: "format_code",
				arguments: [text]
			});

			if (!response) {
				vscode.window.showErrorMessage("No response from server");
				return
			}

			const formatResponse = response as FormatResponse;
			const formattedCode: string = formatResponse.formatted_code;
			const errors: string[] = formatResponse.errors;

			if (formattedCode != null) {
				editor.edit(editBuilder => {
						editBuilder.replace(new vscode.Range(0, 0, document.lineCount, 0), formattedCode);
					}
				);
			}

			let diagnostics: vscode.Diagnostic[] = [];
			diagCollection.clear();

			errors.forEach((error) => {
				let result = extractError(error);

				if (result) {
					let range = new vscode.Range(result.line-1, result.column, result.line-1, result.column + result.identifier.length);
					let message = error.split(":")[1];
					let diagnostic = new vscode.Diagnostic(range, message, vscode.DiagnosticSeverity.Warning);
					diagnostics.push(diagnostic);
				}
			}
			);

			diagCollection.set(document.uri, diagnostics);
		}
		catch (e) {
			vscode.window.showErrorMessage(`Error: ${e}`);
		}
	});

	context.subscriptions.push(format);
}

function extractError(errorMessage: string) {
	const regex = /Line (\d+), Column (\d+):(\w+) '([^']+)'/;
    const match = errorMessage.match(regex);

	if (!match) {
		return null;
	}

	const line = parseInt(match[1]);
	const column = parseInt(match[2]);
	const identifier = match[4];

	return { line, column, identifier };
}

export async function deactivate() : Promise<void> {
	if (client) {
		return client.stop();
	}
}