import * as vscode from "vscode";
import * as path from "path";
import axios from 'axios';
import WebSocket from 'ws';

interface FormatResponse {
	formatted_code: string;
	errors: string[];
}

interface SmellResponse {
	smells: string[];
}

let diagCollection: vscode.DiagnosticCollection;
let outputChannel: vscode.OutputChannel;
const SERVER_URL = "http://localhost:8000";
const WS_URL = "ws://localhost:8000";

const CONNECTION_TIMEOUT = 5000;
const BATCH_SIZE = 5; // Number of files to analyze in parallel

const activeWebSockets: Map<string, WebSocket> = new Map();
let progressBarPromise: Thenable<void> | undefined;
let progressReporter: vscode.Progress<{ message: string }> | undefined;
let progressResolve: ((value: void | PromiseLike<void>) => void) | undefined;
let currentFileIndex = 0;
let totalFiles = 0;

interface FileProgress {
    fileName: string;
    progress: number;
    websocketId: string;
}

const activeFilesProgress: Map<string, FileProgress> = new Map();

// Add cancellation token source
let cancellationTokenSource: vscode.CancellationTokenSource | undefined;

const CANCEL_URL = `${SERVER_URL}/cancel`;

function generateWebSocketId(): string {
    return Math.random().toString(36).substring(2, 15);
}

function createWebSocketConnection(clientId: string): WebSocket {
    const ws = new WebSocket(`${WS_URL}/ws/${clientId}`);
    
    ws.on('message', (data: string) => {
        try {
            const message = JSON.parse(data);
            if (message.type === 'progress') {
                // Update progress for this file
                const fileProgress = activeFilesProgress.get(clientId);
                if (fileProgress) {
                    fileProgress.progress = message.percentage;
                    activeFilesProgress.set(clientId, fileProgress);
                }

                // Update progress display
                if (progressReporter) {
                    if (totalFiles === 1) {
                        // Single file analysis
                        const fileName = path.basename(Array.from(activeFilesProgress.values())[0].fileName);
                        progressReporter.report({ 
                            message: `${fileName} (${message.percentage}%)`
                        });
                    } else {
                        // Multiple files analysis
                        const overallPercentage = Math.round((currentFileIndex / totalFiles) * 100);
                        const activeFilesList = Array.from(activeFilesProgress.values())
                            .map(fp => `${path.basename(fp.fileName)} (${fp.progress}%)`)
                            .join('\n');
                        
                        progressReporter.report({ 
                            message: `Overall: ${overallPercentage}%\n${activeFilesList}`
                        });
                    }
                }
            }
        } catch (e) {
            console.error('Error parsing WebSocket message:', e);
        }
    });

    ws.on('error', (error: Error) => {
        console.error('WebSocket error:', error);
    });

    ws.on('close', (code: number, reason: string) => {
        console.log(`WebSocket closed with code ${code} and reason: ${reason}`);
        activeWebSockets.delete(clientId);
        activeFilesProgress.delete(clientId);
        
        // Check if all files are done
        if (activeFilesProgress.size === 0 && currentFileIndex >= totalFiles) {
            if (progressResolve) {
                progressResolve();
            }
            progressBarPromise = undefined;
            progressReporter = undefined;
            progressResolve = undefined;
        }
    });

    ws.on('open', () => {
        console.log('WebSocket connection established');
    });

    activeWebSockets.set(clientId, ws);
    return ws;
}

async function waitForWebSocketConnection(ws: WebSocket): Promise<void> {
    return new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('WebSocket connection timeout'));
        }, CONNECTION_TIMEOUT);

        ws.on('open', () => {
            clearTimeout(timeout);
            resolve();
        });

        ws.on('error', (error: Error) => {
            clearTimeout(timeout);
            reject(error);
        });
    });
}

async function cancelAnalysis(websocketIds: string[]) {
    try {
        await axios.post(CANCEL_URL, { websocket_ids: websocketIds });
    } catch (e) {
        console.error('Error cancelling analysis:', e);
    }
}

export async function activate(context: vscode.ExtensionContext) : Promise<void> {
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
		vscode.commands.registerCommand('codestyletest.analyze', async () => {
			// Cancel any ongoing analysis
			if (cancellationTokenSource) {
				cancellationTokenSource.cancel();
				// Get all active websocket IDs and cancel them on the server
				const activeIds = Array.from(activeFilesProgress.values()).map(fp => fp.websocketId);
				await cancelAnalysis(activeIds);
				cancellationTokenSource.dispose();
			}
			
			cancellationTokenSource = new vscode.CancellationTokenSource();

			const choice = await vscode.window.showQuickPick(
				["Analyze current file", "Analyze all Java files"],
				{ placeHolder: "Choose an option" }
			);

			if (!choice) {
				vscode.window.showErrorMessage("No option selected");
				return;
			}

			switch (choice) {
				case "Analyze current file":
					const document = getCurrentDocument();
					if (document) {
						totalFiles = 1;
						currentFileIndex = 0;
						activeFilesProgress.clear();
						
						progressBarPromise = vscode.window.withProgress({
							location: vscode.ProgressLocation.Notification,
							title: "Analyzing file",
							cancellable: true
						}, async (progress, token) => {
							progressReporter = progress;
							token.onCancellationRequested(async () => {
								if (cancellationTokenSource) {
									cancellationTokenSource.cancel();
									const activeIds = Array.from(activeFilesProgress.values()).map(fp => fp.websocketId);
									await cancelAnalysis(activeIds);
								}
							});
							
							return new Promise((resolve) => {
								progressResolve = resolve;
								const clientId = generateWebSocketId();
								if (cancellationTokenSource) {
									analyzeSingleFile(document.uri, clientId, cancellationTokenSource.token);
								}
							});
						});
					}
					break;
				case "Analyze all Java files":
					const javaFiles = await getAllJavaFiles();
					if (javaFiles.length > 0) {
						await analyzeAllFiles(javaFiles, cancellationTokenSource.token);
					}
					break;
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
	const configs = vscode.workspace.getConfiguration("codestyletest");
	const settings = JSON.parse(JSON.stringify(configs));

	try {
		const response = await axios.post(`${SERVER_URL}/format`, {
			code: text,
			settings: settings
		});

		const formatResponse = response.data as FormatResponse;
		const formattedCode: string = formatResponse.formatted_code;
		const errors: string[] = formatResponse.errors;

		if (formattedCode != null) {
			const editor = await vscode.window.showTextDocument(document, {preview: false});
			editor.edit(editBuilder => {
				editBuilder.replace(new vscode.Range(0, 0, document.lineCount, 0), formattedCode);
			});
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

async function analyzeAllFiles(files: vscode.Uri[], token: vscode.CancellationToken) {
    totalFiles = files.length;
    currentFileIndex = 0;
    activeFilesProgress.clear();
    
    progressBarPromise = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing all files",
        cancellable: true
    }, async (progress, progressToken) => {
        progressReporter = progress;
        progressToken.onCancellationRequested(async () => {
            if (cancellationTokenSource) {
                cancellationTokenSource.cancel();
                const activeIds = Array.from(activeFilesProgress.values()).map(fp => fp.websocketId);
                await cancelAnalysis(activeIds);
            }
        });
        
        return new Promise((resolve) => {
            progressResolve = resolve;
            
            const processBatch = async (startIndex: number) => {
                if (token.isCancellationRequested) {
                    resolve();
                    return;
                }

                const batch = files.slice(startIndex, startIndex + BATCH_SIZE);
                const batchPromises = batch.map(file => {
                    const clientId = generateWebSocketId();
                    activeFilesProgress.set(clientId, {
                        fileName: file.fsPath,
                        progress: 0,
                        websocketId: clientId
                    });
                    return analyzeSingleFile(file, clientId, token);
                });
                
                await Promise.all(batchPromises);
                
                if (startIndex + BATCH_SIZE < files.length && !token.isCancellationRequested) {
                    processBatch(startIndex + BATCH_SIZE);
                } else {
                    resolve();
                }
            };
            
            processBatch(0);
        });
    });
}

async function analyzeSingleFile(file: vscode.Uri, clientId: string, token: vscode.CancellationToken) {
    if (token.isCancellationRequested) {
        return;
    }

    const document = await vscode.workspace.openTextDocument(file);
    const text = document.getText();
    const ws = createWebSocketConnection(clientId);
    
    try {
        await waitForWebSocketConnection(ws);
        
        if (token.isCancellationRequested) {
            ws.close();
            return;
        }

        activeFilesProgress.set(clientId, {
            fileName: file.fsPath,
            progress: 0,
            websocketId: clientId
        });
        
        const response = await axios.post(`${SERVER_URL}/analyze`, {
            code: text,
            websocket_id: clientId
        });
        
        if (token.isCancellationRequested) {
            return;
        }

        const smellResponse = response.data as SmellResponse;
        const smells: string[] = smellResponse.smells;
        
        if (smells.length > 0) {
            if (!outputChannel) {
                outputChannel = vscode.window.createOutputChannel("Code Smells");
            }
            outputChannel.appendLine(`${file.fsPath}: ${smells.join(", ")}`);
        }
        
        currentFileIndex++;
    } catch (e) {
        if (!token.isCancellationRequested) {
            console.error(`Error analyzing ${file.fsPath}:`, e);
            vscode.window.showErrorMessage(`Error analyzing ${file.fsPath}: ${e}`);
        }
    } finally {
        ws.close();
    }
}
