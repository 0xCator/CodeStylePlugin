import * as vscode from 'vscode';
import { getCurrentContext, getMethodtoCursor, SimpleClassAnalysis } from "./classAnalysis";
import { SERVER_URL } from './extension';
import axios from 'axios';

interface CompletionResponse {
    completion: string;
}

interface CacheEntry {
    completion: string;
    timestamp: number;
}

export class InlineCompletionProvider implements vscode.InlineCompletionItemProvider {
    private debounceTimer: NodeJS.Timeout | null = null;
    private readonly debounceDelay = 300; // 300ms delay
    private cache = new Map<string, CacheEntry>();
    private readonly cacheTimeout = 5 * 60 * 1000; // 5 minutes
    private readonly maxCacheSize = 100; // Maximum number of cached entries

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        // Clear existing timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }

        // Return a promise that resolves after the debounce delay
        return new Promise((resolve) => {
            this.debounceTimer = setTimeout(async () => {
                try {
                    const result = await this.getCompletionItems(document, position, context, token);
                    resolve(result);
                } catch (error) {
                    console.error('Error in debounced completion:', error);
                    resolve([]);
                }
            }, this.debounceDelay);
        });
    }

    private async getCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        // Check if request was cancelled during debounce
        if (token.isCancellationRequested) {
            return [];
        }

        // Get your existing context
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return [];
        }
        if (document.languageId !== 'java') {
            return [];
        }

        const methodChunk = await getMethodtoCursor(editor, position);
        const classContext = await getCurrentContext(document);

        if (!methodChunk || !classContext) {
            return [];
        }

        // Check cancellation again before API call
        if (token.isCancellationRequested) {
            return [];
        }

        // Try to get from cache first
        const cacheKey = this.generateCacheKey(methodChunk, classContext);
        let completion = this.getFromCache(cacheKey);
        
        if (!completion) {
            // Call your API if not in cache
            completion = await this.getCompletionFromAPI(methodChunk, classContext, token);
            
            // Cache the result if successful
            if (completion) {
                this.addToCache(cacheKey, completion);
            }
        }

        if (!completion || token.isCancellationRequested) {
            return [];
        }

        // Create inline completion item
        const item = new vscode.InlineCompletionItem(
            completion,
            new vscode.Range(position, position)
        );

        return [item];
    }

    private async getCompletionFromAPI(code: string, context: SimpleClassAnalysis, token: vscode.CancellationToken): Promise<string | null> {
        try {
            // Create axios request with cancellation support
            const source = axios.CancelToken.source();
            
            // Cancel axios request if VSCode cancellation is requested
            token.onCancellationRequested(() => {
                source.cancel('Request cancelled by VSCode');
            });

            const response = await axios.post(`${SERVER_URL}/autocomplete`, {
                code: code,
                context: context
            }, {
                cancelToken: source.token,
                timeout: 5000 // 5 second timeout
            });

            const data = response.data as CompletionResponse;

            // Additional text processing can be done here if needed

            return data.completion;
        } catch (error) {
            if (axios.isCancel(error)) {
                console.log('Request cancelled:', error.message);
            } else {
                console.error('API call failed:', error);
            }
            return null;
        }
    }

    private generateCacheKey(code: string, context: SimpleClassAnalysis): string {
        // Create a hash-like key from the code and relevant context
        // You might want to include only certain parts of context to avoid over-specific keys
        const contextKey = JSON.stringify({
            className: context.className,
            methods: context.methods?.slice(0, 5) // Just method names
        });
        
        return `${code.trim()}||${contextKey}`;
    }

    private getFromCache(key: string): string | null {
        const entry = this.cache.get(key);
        
        if (!entry) {
            return null;
        }
        
        // Check if cache entry has expired
        if (Date.now() - entry.timestamp > this.cacheTimeout) {
            this.cache.delete(key);
            return null;
        }
        
        return entry.completion;
    }

    private addToCache(key: string, completion: string): void {
        // Implement LRU-like behavior by removing oldest entries when cache is full
        if (this.cache.size >= this.maxCacheSize) {
            const firstKey = this.cache.keys().next().value;
            if (typeof firstKey === 'string') {
                this.cache.delete(firstKey);
            }
        }
        
        this.cache.set(key, {
            completion,
            timestamp: Date.now()
        });
    }

    private clearExpiredCache(): void {
        const now = Date.now();
        for (const [key, entry] of this.cache.entries()) {
            if (now - entry.timestamp > this.cacheTimeout) {
                this.cache.delete(key);
            }
        }
    }

    // Clean up timer and cache when provider is disposed
    dispose() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }
        this.cache.clear();
    }
}