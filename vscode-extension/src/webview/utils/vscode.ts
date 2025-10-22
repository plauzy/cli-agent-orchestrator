// VS Code API available in webview context
declare const acquireVsCodeApi: () => VSCodeAPI;

interface VSCodeAPI {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

class VSCodeAPIWrapper {
  private readonly api: VSCodeAPI | undefined;

  constructor() {
    if (typeof acquireVsCodeApi !== 'undefined') {
      this.api = acquireVsCodeApi();
    }
  }

  public postMessage(message: any): void {
    if (this.api) {
      this.api.postMessage(message);
    }
  }

  public showError(message: string): void {
    this.postMessage({ type: 'error', message });
  }

  public showInfo(message: string): void {
    this.postMessage({ type: 'info', message });
  }

  public openTerminal(sessionName: string): void {
    this.postMessage({ type: 'openTerminal', sessionName });
  }

  public openFile(filePath: string): void {
    this.postMessage({ type: 'openFile', filePath });
  }
}

export const vscode = new VSCodeAPIWrapper();
export type { VSCodeAPI };
