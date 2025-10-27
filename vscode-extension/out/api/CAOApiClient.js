"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CAOApiClient = void 0;
const axios_1 = __importDefault(require("axios"));
class CAOApiClient {
    constructor(baseURL) {
        this.client = axios_1.default.create({
            baseURL,
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }
    // Session endpoints
    async getSessions() {
        const response = await this.client.get('/sessions');
        return response.data;
    }
    async getSession(sessionId) {
        const response = await this.client.get(`/sessions/${sessionId}`);
        return response.data;
    }
    async deleteSession(sessionId) {
        await this.client.delete(`/sessions/${sessionId}`);
    }
    async shutdownAll() {
        const sessions = await this.getSessions();
        await Promise.all(sessions.map(s => this.deleteSession(s.id)));
    }
    // Terminal endpoints
    async getTerminals(sessionId) {
        const url = sessionId ? `/sessions/${sessionId}/terminals` : '/terminals';
        const response = await this.client.get(url);
        return response.data;
    }
    async getTerminal(terminalId) {
        const response = await this.client.get(`/terminals/${terminalId}`);
        return response.data;
    }
    async createTerminal(sessionId, agentProfile) {
        const response = await this.client.post(`/sessions/${sessionId}/terminals`, {
            agent_profile: agentProfile
        });
        return response.data;
    }
    async sendInput(terminalId, input) {
        await this.client.post(`/terminals/${terminalId}/input`, {
            input
        });
    }
    async getOutput(terminalId, mode = 'all') {
        const response = await this.client.get(`/terminals/${terminalId}/output`, {
            params: { mode }
        });
        return response.data.output;
    }
    async deleteTerminal(terminalId) {
        await this.client.delete(`/terminals/${terminalId}`);
    }
    // Inbox endpoints
    async getInboxMessages(terminalId) {
        const response = await this.client.get(`/terminals/${terminalId}/inbox/messages`);
        return response.data;
    }
    async sendMessage(terminalId, senderId, message) {
        const response = await this.client.post(`/terminals/${terminalId}/inbox/messages`, {
            sender_id: senderId,
            message
        });
        return response.data;
    }
    // Flow endpoints
    async getFlows() {
        const response = await this.client.get('/flows');
        return response.data;
    }
    async runFlow(flowName) {
        await this.client.post(`/flows/${flowName}/run`);
    }
    async enableFlow(flowName) {
        await this.client.post(`/flows/${flowName}/enable`);
    }
    async disableFlow(flowName) {
        await this.client.post(`/flows/${flowName}/disable`);
    }
    // Convenience methods
    async launchAgent(agentProfile) {
        // Create a new session first
        const sessionName = `cao-${agentProfile}-${Date.now()}`;
        const response = await this.client.post('/sessions', {
            name: sessionName
        });
        const session = response.data;
        // Then create terminal with agent
        return this.createTerminal(session.id, agentProfile);
    }
    async handoff(callerTerminalId, agentProfile, message) {
        const response = await this.client.post('/orchestration/handoff', {
            caller_terminal_id: callerTerminalId,
            agent_profile: agentProfile,
            message
        });
        return response.data;
    }
    async assign(callerTerminalId, agentProfile, message) {
        const response = await this.client.post('/orchestration/assign', {
            caller_terminal_id: callerTerminalId,
            agent_profile: agentProfile,
            message
        });
        return response.data;
    }
}
exports.CAOApiClient = CAOApiClient;
//# sourceMappingURL=CAOApiClient.js.map