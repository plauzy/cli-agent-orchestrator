// API client for communicating with the CAO FastAPI server
import axios, { AxiosInstance } from 'axios';
import {
  Session,
  Terminal,
  InboxMessage,
  Flow,
  CreateSessionRequest,
  CreateTerminalRequest,
  TerminalOutputResponse,
  SendMessageRequest,
  TerminalStatus
} from '../../shared/types';

export class CaoApiClient {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:9889') {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  // Health check
  async health(): Promise<{ status: string; service: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Session management
  async getSessions(): Promise<Session[]> {
    const response = await this.client.get('/sessions');
    return response.data;
  }

  async getSession(sessionName: string): Promise<Session> {
    const response = await this.client.get(`/sessions/${sessionName}`);
    return response.data;
  }

  async createSession(request: CreateSessionRequest): Promise<Terminal> {
    const response = await this.client.post('/sessions', request);
    return response.data;
  }

  async deleteSession(sessionName: string): Promise<{ success: boolean }> {
    const response = await this.client.delete(`/sessions/${sessionName}`);
    return response.data;
  }

  // Terminal management
  async getTerminals(sessionName: string): Promise<Terminal[]> {
    const response = await this.client.get(`/sessions/${sessionName}/terminals`);
    return response.data;
  }

  async getTerminal(terminalId: string): Promise<Terminal> {
    const response = await this.client.get(`/terminals/${terminalId}`);
    return response.data;
  }

  async createTerminal(
    sessionName: string,
    request: CreateTerminalRequest
  ): Promise<Terminal> {
    const response = await this.client.post(
      `/sessions/${sessionName}/terminals`,
      request
    );
    return response.data;
  }

  async sendInput(terminalId: string, message: string): Promise<{ success: boolean }> {
    const response = await this.client.post(
      `/terminals/${terminalId}/input`,
      null,
      { params: { message } }
    );
    return response.data;
  }

  async getOutput(
    terminalId: string,
    mode: 'full' | 'last' = 'full'
  ): Promise<TerminalOutputResponse> {
    const response = await this.client.get(`/terminals/${terminalId}/output`, {
      params: { mode }
    });
    return response.data;
  }

  async exitTerminal(terminalId: string): Promise<{ success: boolean }> {
    const response = await this.client.post(`/terminals/${terminalId}/exit`);
    return response.data;
  }

  async deleteTerminal(terminalId: string): Promise<{ success: boolean }> {
    const response = await this.client.delete(`/terminals/${terminalId}`);
    return response.data;
  }

  // Messaging
  async sendMessage(
    receiverId: string,
    request: SendMessageRequest
  ): Promise<InboxMessage> {
    const response = await this.client.post(
      `/terminals/${receiverId}/inbox/messages`,
      null,
      {
        params: {
          sender_id: request.sender_id,
          message: request.message
        }
      }
    );
    return response.data;
  }

  // Flows (Note: Flow API endpoints might need to be added to the FastAPI server)
  async getFlows(): Promise<Flow[]> {
    try {
      const response = await this.client.get('/flows');
      return response.data;
    } catch (error) {
      // Flow endpoints might not be implemented in the API yet
      console.warn('Flow API not available:', error);
      return [];
    }
  }

  async enableFlow(flowName: string): Promise<{ success: boolean }> {
    const response = await this.client.post(`/flows/${flowName}/enable`);
    return response.data;
  }

  async disableFlow(flowName: string): Promise<{ success: boolean }> {
    const response = await this.client.post(`/flows/${flowName}/disable`);
    return response.data;
  }

  async runFlow(flowName: string): Promise<{ success: boolean }> {
    const response = await this.client.post(`/flows/${flowName}/run`);
    return response.data;
  }

  // Utility method to wait for terminal status
  async waitForTerminalStatus(
    terminalId: string,
    targetStatus: TerminalStatus,
    timeoutMs: number = 30000,
    pollIntervalMs: number = 1000
  ): Promise<Terminal> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const terminal = await this.getTerminal(terminalId);

      if (terminal.status === targetStatus) {
        return terminal;
      }

      if (terminal.status === TerminalStatus.ERROR) {
        throw new Error(`Terminal ${terminalId} entered ERROR state`);
      }

      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
    }

    throw new Error(
      `Timeout waiting for terminal ${terminalId} to reach ${targetStatus}`
    );
  }

  // Update base URL
  setBaseUrl(url: string): void {
    this.baseUrl = url;
    this.client = axios.create({
      baseURL: url,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
}

// Singleton instance (can be reconfigured)
let apiClient: CaoApiClient | null = null;

export function getApiClient(baseUrl?: string): CaoApiClient {
  if (!apiClient || (baseUrl && apiClient['baseUrl'] !== baseUrl)) {
    apiClient = new CaoApiClient(baseUrl);
  }
  return apiClient;
}
