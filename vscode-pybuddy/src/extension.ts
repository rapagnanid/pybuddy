import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

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

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let lastAnalysis: Map<string, AnalysisResult> = new Map();

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
                analyzeFile(editor.document, false);
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('pybuddy.analyzeOffline', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                analyzeFile(editor.document, true);
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
                    analyzeFile(document, offlineMode);
                }
            }
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

class PyBuddyHoverProvider implements vscode.HoverProvider {
    provideHover(
        document: vscode.TextDocument,
        position: vscode.Position
    ): vscode.Hover | null {
        const filePath = document.uri.fsPath;
        const result = lastAnalysis.get(filePath);

        if (!result) {
            return null;
        }

        const line = position.line + 1;

        // Check anti-patterns
        for (const ap of result.anti_patterns) {
            if (ap.line === line) {
                const md = new vscode.MarkdownString();
                md.appendMarkdown(`**🎯 PyBuddy** — \`${ap.name}\`\n\n`);
                md.appendMarkdown(`${ap.description}\n`);
                md.isTrusted = true;
                return new vscode.Hover(md);
            }
        }

        // Check AI suggestions
        for (const suggestion of result.suggestions) {
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

        return null;
    }
}

export function deactivate() {
    diagnosticCollection?.dispose();
    statusBarItem?.dispose();
}
