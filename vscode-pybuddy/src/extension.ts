import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// --- Interfaces ---

interface AntiPattern {
    name: string;
    line: number;
    code: string;
    description: string;
}

interface Suggestion {
    title: string;
    line: number | null;
    explanation: string;
    code_before: string;
    code_after: string;
    why: string;
}

interface AnalysisResult {
    file: string;
    libraries: string[];
    anti_patterns: AntiPattern[];
    suggestions: Suggestion[];
    summary: string;
}

interface CodeElement {
    kind: string;
    name: string;
    line: number;
    col: number;
    end_line: number;
    end_col: number;
    signature: string;
    docstring: string;
    scope: string;
    code_snippet: string;
    explanation: string;
}

interface ExplainResult {
    file: string;
    elements: CodeElement[];
}

// --- State ---

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let lastAnalysis: Map<string, AnalysisResult> = new Map();
let lastExplain: Map<string, ExplainResult> = new Map();

const MAX_EXPLAIN_CACHE = 20;

// --- Activation ---

export function activate(context: vscode.ExtensionContext) {
    diagnosticCollection = vscode.languages.createDiagnosticCollection('pybuddy');
    context.subscriptions.push(diagnosticCollection);

    // Status bar
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'pybuddy.analyze';
    statusBarItem.text = '$(smiley) PyBuddy';
    statusBarItem.tooltip = 'Click to analyze with PyBuddy';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Commands
    context.subscriptions.push(
        vscode.commands.registerCommand('pybuddy.analyze', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                const config = vscode.workspace.getConfiguration('pybuddy');
                const offlineMode = config.get<boolean>('offlineMode', false);
                runBothAnalyses(editor.document, offlineMode);
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('pybuddy.analyzeOffline', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                runBothAnalyses(editor.document, true);
            }
        })
    );

    // Analyze on save
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument((document) => {
            const config = vscode.workspace.getConfiguration('pybuddy');
            if (config.get<boolean>('analyzeOnSave', true)) {
                if (document.languageId === 'python') {
                    const offlineMode = config.get<boolean>('offlineMode', false);
                    runBothAnalyses(document, offlineMode);
                }
            }
        })
    );

    // Clean up caches when documents close
    context.subscriptions.push(
        vscode.workspace.onDidCloseTextDocument((document) => {
            const filePath = document.uri.fsPath;
            lastAnalysis.delete(filePath);
            lastExplain.delete(filePath);
        })
    );

    // Code actions provider (lightbulb fixes)
    context.subscriptions.push(
        vscode.languages.registerCodeActionsProvider('python', new PyBuddyCodeActionProvider(), {
            providedCodeActionKinds: [vscode.CodeActionKind.QuickFix]
        })
    );

    // Hover provider (sarcastic tooltips)
    context.subscriptions.push(
        vscode.languages.registerHoverProvider('python', new PyBuddyHoverProvider())
    );
}

// --- Run both analyses in parallel ---

async function runBothAnalyses(document: vscode.TextDocument, offline: boolean) {
    const config = vscode.workspace.getConfiguration('pybuddy');
    const enableHover = config.get<boolean>('enableHoverExplanations', true);

    const promises: Promise<void>[] = [analyzeFile(document, offline)];
    if (enableHover) {
        promises.push(explainFile(document, offline));
    }
    await Promise.all(promises);
}

// --- Analyze file (diagnostics + suggestions) ---

async function analyzeFile(document: vscode.TextDocument, offline: boolean) {
    if (document.languageId !== 'python') {
        return;
    }

    const config = vscode.workspace.getConfiguration('pybuddy');
    const pybuddyPath = config.get<string>('pythonPath', 'pybuddy');

    const filePath = document.uri.fsPath;
    const offlineFlag = offline ? '--offline' : '';

    statusBarItem.text = '$(sync~spin) PyBuddy sta pensando...';

    try {
        const { stdout } = await execAsync(
            `${pybuddyPath} analyze "${filePath}" --json ${offlineFlag}`,
            { timeout: 60000 }
        );

        const result: AnalysisResult = JSON.parse(stdout);
        lastAnalysis.set(filePath, result);

        // Build diagnostics
        const diagnostics: vscode.Diagnostic[] = [];

        // Anti-patterns from Layer 1
        for (const ap of result.anti_patterns) {
            const line = Math.max(0, ap.line - 1);
            const range = document.lineAt(line).range;
            const diag = new vscode.Diagnostic(
                range,
                `🎯 ${ap.description}`,
                vscode.DiagnosticSeverity.Warning
            );
            diag.source = 'PyBuddy';
            diag.code = ap.name;
            diagnostics.push(diag);
        }

        // AI suggestions
        for (const suggestion of result.suggestions) {
            if (suggestion.line) {
                const line = Math.max(0, suggestion.line - 1);
                const range = document.lineAt(line).range;
                const diag = new vscode.Diagnostic(
                    range,
                    `💡 ${suggestion.title}\n${suggestion.explanation}`,
                    vscode.DiagnosticSeverity.Information
                );
                diag.source = 'PyBuddy';
                diag.code = 'ai-suggestion';
                diagnostics.push(diag);
            }
        }

        diagnosticCollection.set(document.uri, diagnostics);

        // Show summary in status bar
        const count = diagnostics.length;
        if (count > 0) {
            statusBarItem.text = `$(smiley) PyBuddy: ${count} suggerimenti`;
        } else {
            statusBarItem.text = '$(check) PyBuddy: Codice OK!';
        }

        // Show summary notification if AI analysis
        if (result.summary && !offline) {
            vscode.window.showInformationMessage(`🎤 PyBuddy: ${result.summary}`);
        }

    } catch (error: any) {
        statusBarItem.text = '$(error) PyBuddy: Errore';
        const message = error.stderr || error.message || 'Errore sconosciuto';

        if (message.includes('API key')) {
            vscode.window.showWarningMessage(
                'PyBuddy: API key non configurata. Esegui `pybuddy config set api.key <key>` nel terminale, oppure attiva la modalità offline nelle impostazioni.'
            );
        } else if (message.includes('not found') || message.includes('not recognized')) {
            vscode.window.showErrorMessage(
                'PyBuddy: CLI non trovato. Installa con `pip install pybuddy` e riprova.'
            );
        } else {
            vscode.window.showErrorMessage(`PyBuddy: ${message.substring(0, 200)}`);
        }
    }
}

// --- Explain file (hover elements) ---

async function explainFile(document: vscode.TextDocument, offline: boolean) {
    if (document.languageId !== 'python') {
        return;
    }

    const config = vscode.workspace.getConfiguration('pybuddy');
    const pybuddyPath = config.get<string>('pythonPath', 'pybuddy');
    const filePath = document.uri.fsPath;
    const offlineFlag = offline ? '--offline' : '';

    try {
        const { stdout } = await execAsync(
            `${pybuddyPath} explain "${filePath}" --json ${offlineFlag}`,
            { timeout: 90000 }
        );

        const result: ExplainResult = JSON.parse(stdout);

        // Evict oldest entry if cache is full
        if (lastExplain.size >= MAX_EXPLAIN_CACHE) {
            const firstKey = lastExplain.keys().next().value;
            if (firstKey) {
                lastExplain.delete(firstKey);
            }
        }

        lastExplain.set(filePath, result);
    } catch (error) {
        // Silent failure — hover just won't have explanations
        console.error('PyBuddy explain failed:', error);
    }
}

// --- Find element at cursor position ---

function findElementAtPosition(elements: CodeElement[], position: vscode.Position): CodeElement | null {
    const line = position.line + 1;  // Convert 0-indexed to 1-indexed
    const col = position.character;

    let best: CodeElement | null = null;
    let bestSize = Infinity;

    for (const el of elements) {
        // Check if position falls within element range
        const afterStart = line > el.line || (line === el.line && col >= el.col);
        const beforeEnd = line < el.end_line || (line === el.end_line && col <= el.end_col);

        if (afterStart && beforeEnd) {
            // Prefer the most specific (smallest) element
            const size = (el.end_line - el.line) * 10000 + (el.end_col - el.col);
            if (size < bestSize) {
                best = el;
                bestSize = size;
            }
        }
    }

    return best;
}

// --- Kind display info ---

const KIND_ICONS: Record<string, string> = {
    'function': '🔧',
    'method': '🔧',
    'class': '🏗️',
    'assignment': '📦',
    'for_loop': '🔄',
    'while_loop': '🔄',
    'with_statement': '🔒',
    'list_comp': '✨',
    'dict_comp': '✨',
    'set_comp': '✨',
    'generator': '✨',
    'lambda': '⚡',
    'import': '📥',
    'decorator': '🎀',
    'try_except': '🛡️',
};

const KIND_LABELS: Record<string, string> = {
    'function': 'Funzione',
    'method': 'Metodo',
    'class': 'Classe',
    'assignment': 'Variabile',
    'for_loop': 'Ciclo for',
    'while_loop': 'Ciclo while',
    'with_statement': 'Context manager',
    'list_comp': 'List comprehension',
    'dict_comp': 'Dict comprehension',
    'set_comp': 'Set comprehension',
    'generator': 'Generator',
    'lambda': 'Lambda',
    'import': 'Import',
    'decorator': 'Decoratore',
    'try_except': 'Try/Except',
};

// --- Code Action Provider ---

class PyBuddyCodeActionProvider implements vscode.CodeActionProvider {
    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range,
        context: vscode.CodeActionContext
    ): vscode.CodeAction[] {
        const actions: vscode.CodeAction[] = [];
        const filePath = document.uri.fsPath;
        const result = lastAnalysis.get(filePath);

        if (!result) {
            return actions;
        }

        for (const diag of context.diagnostics) {
            if (diag.source !== 'PyBuddy') {
                continue;
            }

            // Find matching suggestion with a fix
            for (const suggestion of result.suggestions) {
                if (suggestion.line && suggestion.line - 1 === diag.range.start.line && suggestion.code_after) {
                    const action = new vscode.CodeAction(
                        `💡 PyBuddy: ${suggestion.title}`,
                        vscode.CodeActionKind.QuickFix
                    );
                    action.diagnostics = [diag];

                    // Create the edit
                    const edit = new vscode.WorkspaceEdit();

                    // If we have code_before, try to replace it specifically
                    if (suggestion.code_before) {
                        const docText = document.getText();
                        const beforeClean = suggestion.code_before.trim();
                        const idx = docText.indexOf(beforeClean);
                        if (idx !== -1) {
                            const startPos = document.positionAt(idx);
                            const endPos = document.positionAt(idx + beforeClean.length);
                            edit.replace(document.uri, new vscode.Range(startPos, endPos), suggestion.code_after.trim());
                        } else {
                            // Fallback: replace the whole line
                            edit.replace(document.uri, diag.range, suggestion.code_after.trim());
                        }
                    } else {
                        edit.replace(document.uri, diag.range, suggestion.code_after.trim());
                    }

                    action.edit = edit;
                    action.isPreferred = true;
                    actions.push(action);
                }
            }
        }

        return actions;
    }
}

// --- Hover Provider ---

class PyBuddyHoverProvider implements vscode.HoverProvider {
    provideHover(
        document: vscode.TextDocument,
        position: vscode.Position
    ): vscode.Hover | null {
        const filePath = document.uri.fsPath;
        const line = position.line + 1;

        // Priority 1: Anti-patterns and AI suggestions from analysis
        const analysis = lastAnalysis.get(filePath);
        if (analysis) {
            // Check anti-patterns
            for (const ap of analysis.anti_patterns) {
                if (ap.line === line) {
                    const md = new vscode.MarkdownString();
                    md.appendMarkdown(`**🎯 PyBuddy** — \`${ap.name}\`\n\n`);
                    md.appendMarkdown(`${ap.description}\n`);
                    md.isTrusted = true;
                    return new vscode.Hover(md);
                }
            }

            // Check AI suggestions
            for (const suggestion of analysis.suggestions) {
                if (suggestion.line === line) {
                    const md = new vscode.MarkdownString();
                    md.appendMarkdown(`**💡 PyBuddy** — *"${suggestion.title}"*\n\n`);
                    md.appendMarkdown(`${suggestion.explanation}\n\n`);
                    if (suggestion.code_after) {
                        md.appendMarkdown(`**Prova così:**\n`);
                        md.appendCodeblock(suggestion.code_after, 'python');
                    }
                    if (suggestion.why) {
                        md.appendMarkdown(`\n*Perché? ${suggestion.why}*\n`);
                    }
                    md.isTrusted = true;
                    return new vscode.Hover(md);
                }
            }
        }

        // Priority 2: Element explanations from explain cache
        const explain = lastExplain.get(filePath);
        if (explain) {
            const element = findElementAtPosition(explain.elements, position);
            if (element) {
                return this._buildElementHover(element);
            }
        }

        return null;
    }

    private _buildElementHover(element: CodeElement): vscode.Hover {
        const icon = KIND_ICONS[element.kind] || '📌';
        const label = KIND_LABELS[element.kind] || element.kind;
        const md = new vscode.MarkdownString();

        md.appendMarkdown(`**${icon} PyBuddy** — ${label} **${element.name}**\n\n`);

        // Show signature as code block if present
        if (element.signature) {
            md.appendCodeblock(element.signature, 'python');
        }

        if (element.explanation) {
            // AI mode: show the sarcastic explanation
            md.appendMarkdown(`${element.explanation}\n`);
        } else {
            // Offline fallback: show structured info
            const infoParts: string[] = [];
            infoParts.push(`**Tipo:** ${label}`);
            if (element.scope !== 'module') {
                infoParts.push(`**Scope:** \`${element.scope}\``);
            }
            md.appendMarkdown(infoParts.join(' · ') + '\n');

            if (element.docstring) {
                md.appendMarkdown(`\n*${element.docstring}*\n`);
            }
        }

        md.isTrusted = true;
        return new vscode.Hover(md);
    }
}

// --- Deactivation ---

export function deactivate() {
    diagnosticCollection?.dispose();
    statusBarItem?.dispose();
}
