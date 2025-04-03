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

interface SmellResponse {
	smells: string[];
}

let client: LanguageClient | undefined;
let diagCollection: vscode.DiagnosticCollection;
let outputChannel: vscode.OutputChannel;

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

	// Register the command to format code
	context.subscriptions.push(
		vscode.commands.registerCommand('codestyletest.format', () => {
			const choice = vscode.window.showQuickPick(
				["Format current file", "Format all Java files"],
				{ placeHolder: "Choose an option" }
			);

			if (!choice) {
				vscode.window.showErrorMessage("No option selected");
				return;
			}

			choice.then((selectedOption) => {
				switch (selectedOption) {
					case "Format current file":
						const document = getCurrentDocument();
						if (document) {
							formatCode(document);
						}
					break;
					case "Format all Java files":
						getAllJavaFiles().then((javaFiles) => {
							javaFiles.forEach((fileUri) => {
								vscode.workspace.openTextDocument(fileUri).then((doc) => {
									formatCode(doc);
								});
							});
						});
					break;
				}
			})
		})
	);

	// Register the command to analyze smells
	context.subscriptions.push(
		vscode.commands.registerCommand('codestyletest.analyze', () => {
			const choice = vscode.window.showQuickPick(
				["Analyze current file", "Analyze all Java files"],
				{ placeHolder: "Choose an option" }
			);

			if (!choice) {
				vscode.window.showErrorMessage("No option selected");
				return;
			}

			choice.then((selectedOption) => {
				switch (selectedOption) {
					case "Analyze current file":
						const document = getCurrentDocument();
						if (document) {
							analyzeCode(document);
						}
					break;
					case "Analyze all Java files":
						getAllJavaFiles().then((javaFiles) => {
							javaFiles.forEach((fileUri) => {
								vscode.workspace.openTextDocument(fileUri).then((doc) => {
									analyzeCode(doc);
								});
							});
						});
					break;
				}
			})
		})
	);

	// Register listener for configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration("codestyletest")) {
                updateServerConfiguration();
            }
        })
    );
}

function getCurrentDocument() : vscode.TextDocument | undefined {
	const editor = vscode.window.activeTextEditor;
	if (!editor) {
		vscode.window.showErrorMessage("No active text editor found.");
		return;
	}

	const document = editor.document;
	if (document.languageId !== "java") {
		vscode.window.showErrorMessage("Active document is not a Java file.");
		return;
	}
	return document;
}

async function getAllJavaFiles() : Promise<vscode.Uri[]> {
	const javaFiles = await vscode.workspace.findFiles("**/*.java");
	if (javaFiles.length === 0) {
		vscode.window.showInformationMessage("No Java files found in the workspace.");
		return [];
	}

	return javaFiles;
}

async function formatCode(document: vscode.TextDocument) : Promise<void> {
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
			const editor = await vscode.window.showTextDocument(document, {preview: false});
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

async function analyzeCode(document: vscode.TextDocument) : Promise<void> {
	const text = document.getText();
	const fileName = document.fileName;

	try {
		const response = await client?.sendRequest("workspace/executeCommand", {
			command: "analyze_smells",
			arguments: [text]
		});

		if (!response)
			throw new Error("Error: No response from server");

		const smellResponse = response as SmellResponse;
		const smells: string[] = smellResponse.smells;
		const output = smells.join(", ");

		if (output) {
			vscode.window.showInformationMessage("Analysis complete with code smells found in " + fileName);
			if (!outputChannel) {
				outputChannel = vscode.window.createOutputChannel("Code Smells");
			}
			outputChannel.appendLine(fileName + ": " + output);
			outputChannel.show();
		} else {
			vscode.window.showInformationMessage("Analysis complete: No code smells found in " + fileName);
		}
	}
	catch (e) {
		vscode.window.showErrorMessage(`${e}`);
	}
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