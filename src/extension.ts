import * as vscode from "vscode";
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind,
	NotificationType,
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

	const configs = vscode.workspace.getConfiguration("codestyletest");
	const settings = JSON.parse(JSON.stringify(configs));

    let clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: "java" }],
		initializationOptions: settings
    };

    client = new LanguageClient("javaStyleServer", "Java Style Server", serverOptions, clientOptions);
    client.start();

	diagCollection = vscode.languages.createDiagnosticCollection("CodeStyleTest");

	const format = vscode.commands.registerCommand('codestyletest.format', async () => {
		formatCode();
	});

	context.subscriptions.push(format);

	// Register listener for configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration("codestyletest")) {
                updateServerConfiguration();
            }
        })
    );
}

async function formatCode() : Promise<void> {
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
		});

		diagCollection.set(document.uri, diagnostics);
	}
	catch (e) {
		vscode.window.showErrorMessage(`Error: ${e}`);
	}
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

async function updateServerConfiguration() {
    if (!client) return;

    // Get updated settings
    const newConfig = vscode.workspace.getConfiguration("codestyletest");

    // Send them to the LSP via a custom notification
    client.sendNotification(
        new NotificationType("workspace/didChangeConfiguration"),
        { settings: newConfig }
    );
}

export async function deactivate() : Promise<void> {
	if (client) {
		return client.stop();
	}
}