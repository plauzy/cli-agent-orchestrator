import axios, { AxiosInstance } from 'axios';

export interface Session {
    id: string;
    name: string;
    created_at: string;
}

export interface Terminal {
    id: string;
    session_id: string;
    agent_profile: string;
    status: 'IDLE' | 'BUSY' | 'COMPLETED' | 'ERROR';
    created_at: string;
    updated_at: string;
}

export interface InboxMessage {
    id: string;
    terminal_id: string;
    sender_id: string;
    message: string;
    status: 'PENDING' | 'DELIVERED' | 'FAILED';
    created_at: string;
}

export interface Flow {
    id: string;
    name: string;
    schedule: string;
    agent_profile: string;
    enabled: boolean;
    next_run: string | null;
}

export class CAOApiClient {
    private client: AxiosInstance;

    constructor(baseURL: string) {
        this.client = axios.create({
            baseURL,
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }

    // Session endpoints
    async getSessions(): Promise<Session[]> {
        const response = await this.client.get('/sessions');
        return response.data;
    }

    async getSession(sessionId: string): Promise<Session> {
        const response = await this.client.get(`/sessions/${sessionId}`);
        return response.data;
    }

    async deleteSession(sessionId: string): Promise<void> {
        await this.client.delete(`/sessions/${sessionId}`);
    }

    async shutdownAll(): Promise<void> {
        const sessions = await this.getSessions();
        await Promise.all(sessions.map(s => this.deleteSession(s.id)));
    }

    // Terminal endpoints
    async getTerminals(sessionId?: string): Promise<Terminal[]> {
        const url = sessionId ? `/sessions/${sessionId}/terminals` : '/terminals';
        const response = await this.client.get(url);
        return response.data;
    }

    async getTerminal(terminalId: string): Promise<Terminal> {
        const response = await this.client.get(`/terminals/${terminalId}`);
        return response.data;
    }

    async createTerminal(sessionId: string, agentProfile: string): Promise<Terminal> {
        const response = await this.client.post(`/sessions/${sessionId}/terminals`, {
            agent_profile: agentProfile
        });
        return response.data;
    }

    async sendInput(terminalId: string, input: string): Promise<void> {
        await this.client.post(`/terminals/${terminalId}/input`, {
            input
        });
    }

    async getOutput(terminalId: string, mode: 'all' | 'last' = 'all'): Promise<string> {
        const response = await this.client.get(`/terminals/${terminalId}/output`, {
            params: { mode }
        });
        return response.data.output;
    }

    async deleteTerminal(terminalId: string): Promise<void> {
        await this.client.delete(`/terminals/${terminalId}`);
    }

    // Inbox endpoints
    async getInboxMessages(terminalId: string): Promise<InboxMessage[]> {
        const response = await this.client.get(`/terminals/${terminalId}/inbox/messages`);
        return response.data;
    }

    async sendMessage(terminalId: string, senderId: string, message: string): Promise<InboxMessage> {
        const response = await this.client.post(`/terminals/${terminalId}/inbox/messages`, {
            sender_id: senderId,
            message
        });
        return response.data;
    }

    // Flow endpoints
    async getFlows(): Promise<Flow[]> {
        const response = await this.client.get('/flows');
        return response.data;
    }

    async runFlow(flowName: string): Promise<void> {
        await this.client.post(`/flows/${flowName}/run`);
    }

    async enableFlow(flowName: string): Promise<void> {
        await this.client.post(`/flows/${flowName}/enable`);
    }

    async disableFlow(flowName: string): Promise<void> {
        await this.client.post(`/flows/${flowName}/disable`);
    }

    // Convenience methods
    async launchAgent(agentProfile: string): Promise<Terminal> {
        // Create a new session first
        const sessionName = `cao-${agentProfile}-${Date.now()}`;
        const response = await this.client.post('/sessions', {
            name: sessionName
        });
        const session = response.data;

        // Then create terminal with agent
        return this.createTerminal(session.id, agentProfile);
    }

    async handoff(
        callerTerminalId: string,
        agentProfile: string,
        message: string
    ): Promise<{ output: string; terminal_id: string }> {
        const response = await this.client.post('/orchestration/handoff', {
            caller_terminal_id: callerTerminalId,
            agent_profile: agentProfile,
            message
        });
        return response.data;
    }

    async assign(
        callerTerminalId: string,
        agentProfile: string,
        message: string
    ): Promise<{ terminal_id: string }> {
        const response = await this.client.post('/orchestration/assign', {
            caller_terminal_id: callerTerminalId,
            agent_profile: agentProfile,
            message
        });
        return response.data;
    }
}
