import axios, { AxiosInstance } from 'axios';
import {
  Session,
  Terminal,
  AgentProfile,
  Flow,
  OrchestrationRequest,
  ServerHealth,
} from '../types';

export class CAOClient {
  private api: AxiosInstance;

  constructor(baseURL: string = 'http://localhost:9889') {
    this.api = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Health check
  async getHealth(): Promise<ServerHealth> {
    const response = await this.api.get('/health');
    return response.data;
  }

  // Session management
  async getSessions(): Promise<Session[]> {
    const response = await this.api.get('/sessions');
    return response.data.sessions || [];
  }

  async getSession(sessionId: string): Promise<Session> {
    const response = await this.api.get(`/sessions/${sessionId}`);
    return response.data;
  }

  async createSession(name: string, agents: string[]): Promise<Session> {
    const response = await this.api.post('/sessions', {
      name,
      agents,
    });
    return response.data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.api.delete(`/sessions/${sessionId}`);
  }

  // Terminal management
  async getTerminals(sessionId: string): Promise<Terminal[]> {
    const response = await this.api.get(`/sessions/${sessionId}/terminals`);
    return response.data.terminals || [];
  }

  async getTerminal(terminalId: string): Promise<Terminal> {
    const response = await this.api.get(`/terminals/${terminalId}`);
    return response.data;
  }

  async createTerminal(
    sessionId: string,
    agentProfile: string,
    message?: string
  ): Promise<Terminal> {
    const response = await this.api.post(`/sessions/${sessionId}/terminals`, {
      agent_profile: agentProfile,
      message,
    });
    return response.data;
  }

  async sendMessage(terminalId: string, message: string): Promise<void> {
    await this.api.post(`/terminals/${terminalId}/messages`, {
      message,
    });
  }

  async getTerminalOutput(terminalId: string): Promise<string> {
    const response = await this.api.get(`/terminals/${terminalId}/output`);
    return response.data.output || '';
  }

  // Orchestration
  async handoff(
    fromTerminalId: string,
    agentProfile: string,
    message: string
  ): Promise<Terminal> {
    const response = await this.api.post(`/terminals/${fromTerminalId}/handoff`, {
      agent_profile: agentProfile,
      message,
    });
    return response.data;
  }

  async assign(
    fromTerminalId: string,
    agentProfile: string,
    message: string
  ): Promise<Terminal> {
    const response = await this.api.post(`/terminals/${fromTerminalId}/assign`, {
      agent_profile: agentProfile,
      message,
    });
    return response.data;
  }

  // Agent profiles
  async getAgentProfiles(): Promise<AgentProfile[]> {
    const response = await this.api.get('/agent-profiles');
    return response.data.profiles || [];
  }

  async installAgentProfile(source: string): Promise<AgentProfile> {
    const response = await this.api.post('/agent-profiles', {
      source,
    });
    return response.data;
  }

  // Flows
  async getFlows(): Promise<Flow[]> {
    const response = await this.api.get('/flows');
    return response.data.flows || [];
  }

  async addFlow(flowDefinition: string): Promise<Flow> {
    const response = await this.api.post('/flows', {
      definition: flowDefinition,
    });
    return response.data;
  }

  async removeFlow(flowName: string): Promise<void> {
    await this.api.delete(`/flows/${flowName}`);
  }

  async enableFlow(flowName: string): Promise<void> {
    await this.api.post(`/flows/${flowName}/enable`);
  }

  async disableFlow(flowName: string): Promise<void> {
    await this.api.post(`/flows/${flowName}/disable`);
  }

  async runFlow(flowName: string): Promise<void> {
    await this.api.post(`/flows/${flowName}/run`);
  }
}
