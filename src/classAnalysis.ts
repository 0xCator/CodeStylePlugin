import * as vscode from 'vscode';

interface ClassMember {
    name: string;
    kind: 'method' | 'field';
    visibility: 'public' | 'private' | 'protected' | 'package';
    static: boolean;
    type: string;
    signature?: string; // For methods
    inherited?: boolean;
    source?: string; // Class where the member is defined
}

interface ClassAnalysis {
    className: string;
    methods: ClassMember[];
    fields: ClassMember[];
    compositionMembers: ClassMember[]; // Methods/fields from composed objects
    inheritedMembers: ClassMember[]; // Methods/fields from parent classes
    superClass?: string;
    interfaces: string[];
}

export interface SimpleClassAnalysis {
    className: string;
    methods: string[];
    fields: string[];
    compositionMembers: string[];
    inheritedMembers: string[];
    superClass?: string;
    interfaces: string[];
}

export async function getCurrentContext(document: vscode.TextDocument): Promise<SimpleClassAnalysis | null> {
    try {
        // Find the first class symbol (assuming single class per file)
        const classSymbol = await getClassSymbol(document);
        if (!classSymbol) {
            return null;
        }

        const analysis: ClassAnalysis = {
            className: classSymbol.name,
            methods: [],
            fields: [],
            compositionMembers: [],
            inheritedMembers: [],
            interfaces: []
        };

        // Get type hierarchy information using the class symbol's position
        const typeHierarchy = await getTypeHierarchy(document.uri, classSymbol.selectionRange.start);
        
        // Analyze direct members of the class
        await analyzeDirectMembers(classSymbol, analysis, document);
        
        // Analyze inherited members from parent classes
        if (typeHierarchy) {
            await analyzeInheritedMembers(typeHierarchy, analysis);
        }
        
        // Analyze composition members (fields that are objects with their own methods)
        await analyzeCompositionMembers(document.uri, classSymbol, analysis);

        return {
            className: analysis.className,
            methods: analysis.methods.map(formatMember),
            fields: analysis.fields.map(formatMember),
            compositionMembers: analysis.compositionMembers.map(formatMember),
            inheritedMembers: analysis.inheritedMembers.map(formatMember),
            superClass: analysis.superClass,
            interfaces: analysis.interfaces
        };

    } catch (error) {
        console.error('Error analyzing Java class:', error);
        return null;
    }
}

function formatMember(member: ClassMember): string {
    const visibility = member.visibility === 'package' ? '' : `${member.visibility} `;
    const staticModifier = member.static ? 'static ' : '';
    return `${visibility}${staticModifier}${member.type} ${member.name}`;
}

export async function getMethodtoCursor(editor: vscode.TextEditor, cursorPos: vscode.Position): Promise<string | null> {
    const document = editor.document;
    const classSymbol = await getClassSymbol(document);
    if (!classSymbol) {
        return null;
    }

    for (const child of classSymbol.children) {
        if (child.kind === vscode.SymbolKind.Method && child.range.contains(cursorPos)) {
            const methodText = editor.document.getText(new vscode.Range(child.range.start, cursorPos));
            return methodText;
        }
    }

    return null;
}

export async function getClassSymbol(document: vscode.TextDocument): Promise<vscode.DocumentSymbol | undefined> {
    const documentSymbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );

    if (!documentSymbols) {
        return undefined;
    }

    // Find the first class symbol (assuming single class per file)
    const classSymbol = documentSymbols.find(symbol => symbol.kind === vscode.SymbolKind.Class);
    return classSymbol;
}

async function getTypeHierarchy(uri: vscode.Uri, position: vscode.Position): Promise<vscode.TypeHierarchyItem[] | null> {
    try {
        const items = await vscode.commands.executeCommand<vscode.TypeHierarchyItem[]>(
            'vscode.prepareTypeHierarchy',
            uri,
            position
        );

        if (items && items.length > 0) {
            // Get supertypes (parent classes and interfaces)
            const supertypes = await vscode.commands.executeCommand<vscode.TypeHierarchyItem[]>(
                'vscode.provideTypeHierarchySupertypes',
                items[0]
            );
            return supertypes;
        }
        return null;
    } catch (error) {
        console.error('Error getting type hierarchy:', error);
        return null;
    }
}

async function analyzeDirectMembers(classSymbol: vscode.DocumentSymbol, analysis: ClassAnalysis, document: vscode.TextDocument): Promise<void> {
    for (const child of classSymbol.children) {
        // Get hover information for better type and modifier details
        const hoverInfo = await vscode.commands.executeCommand<vscode.Hover[]>(
            'vscode.executeHoverProvider',
            document.uri,
            child.selectionRange.start
        );

        const hoverText = hoverInfo && hoverInfo.length > 0 
            ? extractTextFromHover(hoverInfo[0]) 
            : '';

        const member: ClassMember = {
            name: child.name,
            kind: child.kind === vscode.SymbolKind.Method || child.kind === vscode.SymbolKind.Constructor ? 'method' : 'field',
            visibility: parseVisibility(hoverText) || parseVisibilityFromContext(child, document),
            static: isStatic(hoverText) || await isStaticFromContext(child, document),
            type: parseType(hoverText) || await getTypeFromContext(child, document),
            inherited: false,
            source: analysis.className
        };

        if (child.kind === vscode.SymbolKind.Method) {
            member.signature = hoverText || child.detail || '';
            analysis.methods.push(member);
        } else if (child.kind === vscode.SymbolKind.Field || child.kind === vscode.SymbolKind.Property) {
            analysis.fields.push(member);
        }
    }
}

async function analyzeInheritedMembers(
    supertypes: vscode.TypeHierarchyItem[],
    analysis: ClassAnalysis
): Promise<void> {
    for (const supertype of supertypes) {
        if (supertype.kind === vscode.SymbolKind.Class) {
            analysis.superClass = supertype.name;
        } else if (supertype.kind === vscode.SymbolKind.Interface) {
            analysis.interfaces.push(supertype.name);
        }

        // Get members from the supertype
        const supertypeSymbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            supertype.uri
        );

        if (supertypeSymbols) {
            const supertypeClass = supertypeSymbols.find(s => s.name === supertype.name);
            if (supertypeClass) {
                for (const child of supertypeClass.children) {
                    const visibility = parseVisibilityFromContext(child, await vscode.workspace.openTextDocument(supertype.uri));
                    
                    // Only include public and protected members (accessible to subclasses)
                    if (visibility === 'public' || visibility === 'protected') {
                        const member: ClassMember = {
                            name: child.name,
                            kind: child.kind === vscode.SymbolKind.Method || child.kind === vscode.SymbolKind.Constructor ? 'method' : 'field',
                            visibility,
                            static: await isStaticFromContext(child, await vscode.workspace.openTextDocument(supertype.uri)),
                            type: await getTypeFromContext(child, await vscode.workspace.openTextDocument(supertype.uri)),
                            inherited: true,
                            source: supertype.name
                        };

                        if (member.kind === 'method') {
                            member.signature = child.detail || '';
                        }

                        analysis.inheritedMembers.push(member);
                    }
                }
            }
        }
    }
}

async function analyzeCompositionMembers(
    uri: vscode.Uri,
    classSymbol: vscode.DocumentSymbol,
    analysis: ClassAnalysis
): Promise<void> {
    const document = await vscode.workspace.openTextDocument(uri);
    
    // Find field declarations that are object types
    for (const field of classSymbol.children) {
        if (field.kind === vscode.SymbolKind.Field || field.kind === vscode.SymbolKind.Property) {
            // Use hover provider like in analyzeDirectMembers
            const hoverInfo = await vscode.commands.executeCommand<vscode.Hover[]>(
                'vscode.executeHoverProvider',
                uri,
                field.selectionRange.start
            );

            const hoverText = hoverInfo && hoverInfo.length > 0 
                ? extractTextFromHover(hoverInfo[0]) 
                : '';

            const fieldType = parseType(hoverText) || await getTypeFromContext(field, document);
            
            // Skip primitive types and common Java types
            if (isPrimitiveOrCommonType(fieldType)) {
                continue;
            }

            const typePosition = findTypePositionInField(document, field, fieldType);

            // Try to find the definition of the field type
            const definitions = await vscode.commands.executeCommand<vscode.Location[]>(
                'vscode.executeDefinitionProvider',
                uri,
                typePosition
            );

            if (definitions && definitions.length > 0) {
                const typeDefinition = definitions[0];
                const typeSymbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
                    'vscode.executeDocumentSymbolProvider',
                    typeDefinition.uri
                );

                if (typeSymbols) {
                    const typeClass = typeSymbols.find(s => s.name === fieldType);
                    if (typeClass) {
                        for (const member of typeClass.children) {
                            const visibility = parseVisibilityFromContext(member, await vscode.workspace.openTextDocument(typeDefinition.uri));
                            
                            // Only include public members for composition
                            if (visibility === 'public') {
                                const compositionMember: ClassMember = {
                                    name: `${field.name}.${member.name}`,
                                    kind: member.kind === vscode.SymbolKind.Method || member.kind === vscode.SymbolKind.Constructor ? 'method' : 'field',
                                    visibility,
                                    static: await isStaticFromContext(member, await vscode.workspace.openTextDocument(typeDefinition.uri)),
                                    type: await getTypeFromContext(member, await vscode.workspace.openTextDocument(typeDefinition.uri)),
                                    inherited: false,
                                    source: `${fieldType} (via ${field.name})`
                                };

                                if (compositionMember.kind === 'method') {
                                    compositionMember.signature = member.detail || '';
                                }

                                analysis.compositionMembers.push(compositionMember);
                            }
                        }
                    }
                }
            }
        }
    }
}

function findTypePositionInField(document: vscode.TextDocument, field: vscode.DocumentSymbol, typeName: string): vscode.Position | null {
    const line = document.lineAt(field.range.start.line);
    const lineText = line.text;
    
    // Find the position of the type name in the line
    const typeIndex = lineText.indexOf(typeName);
    if (typeIndex !== -1) {
        return new vscode.Position(field.range.start.line, typeIndex);
    }
    
    return null;
}

// Helper functions for parsing symbol information
function extractTextFromHover(hover: vscode.Hover): string {
    if (!hover.contents || hover.contents.length === 0) {
        return '';
    }

    let text = '';
    for (const content of hover.contents) {
        if (typeof content === 'string') {
            text += content;
        } else if (content instanceof vscode.MarkdownString) {
            text += content.value;
        } else if ('language' in content && 'value' in content) {
            // It's a MarkedString with language and value
            text += content.value;
        }
    }
    
    // Clean up markdown formatting
    return text.replace(/```java\n?|```\n?/g, '').replace(/\*\*/g, '').trim();
}

function parseVisibility(hoverText: string): 'public' | 'private' | 'protected' | 'package' | null {
    if (!hoverText) return null;
    if (hoverText.includes('private')) return 'private';
    if (hoverText.includes('protected')) return 'protected';
    if (hoverText.includes('public')) return 'public';
    return null;
}

function parseVisibilityFromContext(symbol: vscode.DocumentSymbol, document: vscode.TextDocument): 'public' | 'private' | 'protected' | 'package' {
    // Get the text of the line where the symbol is defined
    const line = document.lineAt(symbol.range.start.line);
    const lineText = line.text;
    
    if (lineText.includes('private')) return 'private';
    if (lineText.includes('protected')) return 'protected';
    if (lineText.includes('public')) return 'public';
    return 'package';
}

function isStatic(hoverText: string): boolean {
    return hoverText.includes('static');
}

async function isStaticFromContext(symbol: vscode.DocumentSymbol, document: vscode.TextDocument): Promise<boolean> {
    // Get the text of the line where the symbol is defined
    const line = document.lineAt(symbol.range.start.line);
    const lineText = line.text;
    
    return lineText.includes('static');
}

function parseType(hoverText: string): string | null {
    if (!hoverText) return null;
    
    // Try to extract type from hover text (which often contains full signature)
    // Look for patterns like "public static String methodName" or "private int fieldName"
    const typeMatch = hoverText.match(/(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*([A-Za-z_$][A-Za-z0-9_$<>,\[\]\s]*?)\s+[A-Za-z_$]/);
    if (typeMatch && typeMatch[1]) {
        return typeMatch[1].trim();
    }
    
    return null;
}

async function getTypeFromContext(symbol: vscode.DocumentSymbol, document: vscode.TextDocument): Promise<string> {
    // For fields, try to extract type from the line
    if (symbol.kind === vscode.SymbolKind.Field || symbol.kind === vscode.SymbolKind.Property) {
        const line = document.lineAt(symbol.range.start.line);
        const lineText = line.text.trim();
        
        // Simple regex to extract type from field declaration
        // Matches patterns like: private String fieldName, public static int count, etc.
        const fieldMatch = lineText.match(/(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*([A-Za-z_$][A-Za-z0-9_$<>,\[\]\s]*?)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*[=;]/);
        if (fieldMatch && fieldMatch[1]) {
            return fieldMatch[1].trim();
        }
    }
    
    // For methods, try to extract return type
    if (symbol.kind === vscode.SymbolKind.Method) {
        const line = document.lineAt(symbol.range.start.line);
        const lineText = line.text.trim();
        
        // Simple regex to extract return type from method declaration
        const methodMatch = lineText.match(/(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*([A-Za-z_$][A-Za-z0-9_$<>,\[\]\s]*?)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\(/);
        if (methodMatch && methodMatch[1]) {
            return methodMatch[1].trim();
        }
    }
    
    return 'unknown';
}

function isPrimitiveOrCommonType(type: string): boolean {
    const primitiveAndCommonTypes = [
        'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short',
        'Integer', 'Long', 'Double', 'Float', 'Boolean', 'Character', 'Byte', 'Short',
        'String', 'Object', 'List', 'ArrayList', 'Map', 'HashMap', 'Set', 'HashSet'
    ];
    
    return primitiveAndCommonTypes.some(primitive => 
        type === primitive || type.startsWith(primitive + '<')
    );
}