import { useCallback } from 'react';
import { VSCodeMessage } from '../types';

// Acquire VS Code API
declare global {
  interface Window {
    acquireVsCodeApi: () => any;
  }
}

const vscode = window.acquireVsCodeApi?.() || {
  postMessage: (message: any) => {
    console.log('Mock VSCode API:', message);
  },
  setState: (_state: any) => {},
  getState: () => ({})
};

export function useVSCodeAPI() {
  const sendMessage = useCallback((message: VSCodeMessage) => {
    vscode.postMessage(message);
  }, []);

  const onMessage = useCallback((handler: (message: any) => void) => {
    const messageHandler = (event: MessageEvent) => {
      const message = event.data;
      handler(message);
    };

    window.addEventListener('message', messageHandler);
    return () => window.removeEventListener('message', messageHandler);
  }, []);

  // Note: setState and getState available but not currently used
  // const setState = useCallback((state: any) => {
  //   vscode.setState(state);
  // }, []);

  // const getState = useCallback(() => {
  //   return vscode.getState();
  // }, []);

  return {
    sendMessage,
    onMessage
  };
}
