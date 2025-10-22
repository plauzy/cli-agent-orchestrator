import React, { useState, useEffect } from 'react';
import { CAOClient } from '../api/caoClient';
import { AgentProfile } from '../types';
import { vscode } from '../utils/vscode';

interface AgentProfilesProps {
  client: CAOClient;
}

export const AgentProfiles: React.FC<AgentProfilesProps> = ({ client }) => {
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInstallDialog, setShowInstallDialog] = useState(false);
  const [installSource, setInstallSource] = useState('');

  useEffect(() => {
    loadProfiles();
  }, []);

  const loadProfiles = async () => {
    try {
      const data = await client.getAgentProfiles();
      setProfiles(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load agent profiles');
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async () => {
    if (!installSource.trim()) {
      vscode.showError('Install source is required');
      return;
    }

    try {
      await client.installAgentProfile(installSource);
      setShowInstallDialog(false);
      setInstallSource('');
      await loadProfiles();
      vscode.showInfo('Agent profile installed successfully');
    } catch (err: any) {
      vscode.showError(`Failed to install agent profile: ${err.message}`);
    }
  };

  const handleViewProfile = (profile: AgentProfile) => {
    vscode.openFile(profile.path);
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert error">
        {error}
      </div>
    );
  }

  return (
    <div className="agent-profiles">
      <div className="section">
        <div className="section-header">
          <h2>Agent Profiles</h2>
          <button className="primary" onClick={() => setShowInstallDialog(true)}>
            + Install Profile
          </button>
        </div>

        <div className="alert info" style={{ marginBottom: '15px' }}>
          Agent profiles define the behavior and capabilities of agents.
          Built-in profiles: <code>code_supervisor</code>, <code>developer</code>, <code>reviewer</code>
        </div>

        {profiles.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-message">
              No agent profiles found. Install profiles using the CLI.
            </div>
          </div>
        ) : (
          <div className="profiles-grid">
            {profiles.map(profile => (
              <div key={profile.name} className="profile-card card">
                <div className="profile-header">
                  <div className="profile-icon">🤖</div>
                  <div className="profile-info">
                    <h3 className="profile-name">{profile.name}</h3>
                    {profile.description && (
                      <p className="profile-description">{profile.description}</p>
                    )}
                  </div>
                </div>

                <div className="profile-footer">
                  <div className="profile-path" title={profile.path}>
                    📁 {profile.path.split('/').pop()}
                  </div>
                  <button
                    className="secondary"
                    onClick={() => handleViewProfile(profile)}
                  >
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showInstallDialog && (
        <div className="dialog-overlay" onClick={() => setShowInstallDialog(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <h3>Install Agent Profile</h3>
            <div className="form-group">
              <label>Source</label>
              <input
                type="text"
                value={installSource}
                onChange={e => setInstallSource(e.target.value)}
                placeholder="code_supervisor, ./my-agent.md, or https://..."
              />
              <div className="help-text">
                Enter a built-in profile name, local file path, or URL
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setShowInstallDialog(false)}>
                Cancel
              </button>
              <button className="primary" onClick={handleInstall}>
                Install
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .profiles-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 15px;
        }

        .profile-card {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }

        .profile-header {
          display: flex;
          gap: 12px;
          margin-bottom: 15px;
        }

        .profile-icon {
          font-size: 32px;
          line-height: 1;
        }

        .profile-info {
          flex: 1;
        }

        .profile-name {
          font-size: 15px;
          font-weight: 600;
          margin-bottom: 5px;
        }

        .profile-description {
          font-size: 12px;
          opacity: 0.8;
          line-height: 1.4;
        }

        .profile-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 12px;
          border-top: 1px solid var(--vscode-panel-border);
        }

        .profile-path {
          font-size: 11px;
          opacity: 0.7;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
          margin-right: 10px;
        }
      `}</style>
    </div>
  );
};
